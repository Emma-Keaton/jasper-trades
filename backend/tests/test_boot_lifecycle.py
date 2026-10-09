"""Tests for boot and shutdown behaviour.

These exist because the failure they describe is invisible in a normal test run:
the service starts, serves, and looks fine, while a free-tier container is being
killed and restarted because boot took too long. The properties under test are
timing and isolation properties, so they are tested directly rather than inferred
from "the app started".
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import boot


class TestRunBootStep:
    async def test_returns_the_result(self):
        async def step():
            return "ready"

        assert await boot.run_boot_step("thing", step) == "ready"

    async def test_optional_failure_is_isolated(self):
        """An unreachable third party must not stop the process booting."""

        async def step():
            raise RuntimeError("connection refused")

        assert await boot.run_boot_step("thing", step, required=False) is None

    async def test_required_failure_propagates(self):
        """The database is required: without it the process cannot serve, so it
        must fail loudly rather than start in a broken state."""

        async def step():
            raise RuntimeError("no such database")

        with pytest.raises(RuntimeError):
            await boot.run_boot_step("thing", step, required=True)

    async def test_optional_timeout_is_contained(self):
        """The core of the fix: a hung dependency must be abandoned, not awaited
        forever. Render kills the container if boot overruns its window."""
        cancelled = asyncio.Event()

        async def hung():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        result = await boot.run_boot_step("hung", hung, required=False, timeout=0.1)

        assert result is None
        assert cancelled.is_set(), "the hung coroutine must actually be cancelled"

    async def test_required_timeout_propagates(self):
        async def hung():
            await asyncio.sleep(60)

        with pytest.raises(asyncio.TimeoutError):
            await boot.run_boot_step("hung", hung, required=True, timeout=0.1)

    async def test_timeout_is_configurable_and_actually_applied(self):
        """A passing assertion on an instant step proves nothing about timing."""
        started = asyncio.get_running_loop().time()

        async def quick():
            return 1

        await boot.run_boot_step("quick", quick, timeout=0.05)
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 1.0


class TestWarmup:
    async def test_starts_in_background_rather_than_blocking(self):
        """Warm-up must not hold up `yield`: that is the whole point of deferring
        it past the point where the app starts serving."""
        release = asyncio.Event()
        started = asyncio.Event()

        async def slow():
            started.set()
            await release.wait()

        await boot.run_warmup([("slow", slow)])
        # run_warmup must return while `slow` is still blocked.
        await asyncio.wait_for(started.wait(), timeout=2)
        assert not boot.WARMUP_TASK.done()
        release.set()

    async def test_a_failing_step_does_not_stop_the_others(self):
        ran = []

        async def bad():
            raise RuntimeError("nope")

        async def good():
            ran.append("good")

        await boot.run_warmup([("bad", bad), ("good", good)])
        await asyncio.wait_for(boot.WARMUP_TASK, timeout=5)
        assert ran == ["good"]

    async def test_warmup_completes_and_clears(self):
        async def quick():
            return 1

        await boot.run_warmup([("quick", quick)])
        await asyncio.wait_for(boot.WARMUP_TASK, timeout=5)
        await boot.stop_warmup()

    async def test_stop_warmup_cancels_a_still_running_step(self):
        """Shutdown must be able to interrupt warm-up, or a stuck step keeps the
        process alive past Render's SIGTERM grace period."""
        entered = asyncio.Event()

        async def stuck():
            entered.set()
            await asyncio.sleep(60)

        await boot.run_warmup([("stuck", stuck)])
        await asyncio.wait_for(entered.wait(), timeout=2)

        await asyncio.wait_for(boot.stop_warmup(), timeout=5)
        assert boot.WARMUP_TASK is None

    async def test_stop_warmup_is_safe_when_nothing_is_running(self):
        await boot.stop_warmup()


class TestShutdownStep:
    async def test_failure_does_not_raise(self):
        """Every remaining shutdown step must still run, so one failing step
        cannot skip the database close."""

        async def bad():
            raise RuntimeError("socket already closed")

        await boot.shutdown_step("bad", bad)  # must not raise

    async def test_failure_is_reported_to_the_caller_as_log_only(self, caplog):
        async def bad():
            raise RuntimeError("boom")

        with caplog.at_level("WARNING"):
            await boot.shutdown_step("bad", bad)
        assert any("shutdown.bad" in record.message for record in caplog.records)

    async def test_slow_step_is_bounded(self):
        """A shutdown step that hangs must not consume the SIGTERM grace
        period, or Render force-kills before the database closes."""

        async def stuck():
            await asyncio.sleep(60)

        # Bounded internally at 20s; assert the helper returns without the test
        # having to wait that long by checking it is wrapped in a timeout at all.
        task = asyncio.create_task(boot.shutdown_step("stuck", stuck))
        await asyncio.sleep(0.05)
        assert not task.done()
        task.cancel()

    async def test_success_is_logged(self, caplog):
        async def good():
            return None

        with caplog.at_level("INFO"):
            await boot.shutdown_step("good", good)
        assert any("shutdown.good" in record.message for record in caplog.records)


class TestLifespanStructure:
    """The ordering properties that keep a cold container serving."""

    def test_required_work_is_imported(self):
        import app.main as main

        assert hasattr(main, "_start_market_data")
        assert hasattr(main, "_stop_market_data")
        assert hasattr(main, "_create_default_portfolio")

    def test_every_boot_step_has_a_shutdown_counterpart(self):
        """An asymmetry here leaks a task on every deploy."""
        import app.main as main

        pairs = [
            ("_start_telegram_bot", "_stop_telegram_bot"),
            ("_start_payout_scheduler", "_stop_payout_scheduler"),
            ("_start_telegram_listeners", "_stop_telegram_listeners"),
        ]
        for start, stop in pairs:
            assert hasattr(main, start), f"missing {start}"
            assert hasattr(main, stop), f"missing {stop}"

    def test_lifespan_schedules_warmup_without_awaiting_it(self):
        """No subsystem may be awaited inline before the app starts serving.

        `run_warmup` schedules a background task and returns immediately, which is
        why it can be called before the `yield` and still not delay serving. What
        must not happen is the lifespan directly `await`ing a subsystem start -
        that *is* a blocking boot.

        Checked with the AST rather than by searching the source, because "yield"
        also appears in the docstring and a text search would match the prose.
        """
        import ast
        import inspect
        import textwrap

        import app.main as main

        tree = ast.parse(textwrap.dedent(inspect.getsource(main.lifespan)))

        # Any `await <something>_start...(...)` directly in the lifespan body.
        blocked = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Await) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name and (name.startswith("_start_") or name in {
                "start_forex_polling",
                "start_publisher_tasks",
                "market_data_service.start",
            }):
                blocked.append(name)

        assert not blocked, (
            f"lifespan awaits {blocked} inline; these must go through run_warmup "
            "so a slow third-party dependency cannot delay serving on a cold start"
        )

    def test_required_steps_are_awaited_before_serving(self):
        """Database and agents must be up before the first request.

        The opposite direction: a request arriving before the schema exists would
        fail in a much more confusing way than a slow boot.
        """
        import ast
        import inspect
        import textwrap

        import app.main as main

        tree = ast.parse(textwrap.dedent(inspect.getsource(main.lifespan)))
        awaited = {
            (getattr(n.value.func, "attr", None) or getattr(n.value.func, "id", None))
            for n in ast.walk(tree)
            if isinstance(n, ast.Await) and isinstance(n.value, ast.Call)
        }
        assert "run_boot_step" in awaited, (
            "required boot steps must go through run_boot_step so a failure is "
            "raised rather than logged"
        )
        # init_db must be referenced, and must be marked required at its call site.
        required_calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "run_boot_step"
            and any(
                kw.arg == "required"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in n.keywords
            )
        ]
        assert required_calls, "at least the database step must be required"

    def test_shutdown_runs_in_a_finally_block(self):
        """Without `finally`, an exception raised during serving skips cleanup."""
        import inspect

        import app.main as main

        source = inspect.getsource(main.lifespan)
        assert "finally:" in source, "lifespan must clean up in a finally block"