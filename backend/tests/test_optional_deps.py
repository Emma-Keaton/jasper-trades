"""Optional-dependency handling: probing, the memory gate, and the deferred install.

The soft tier exists so a missing package degrades one capability instead of
refusing to boot. Two properties matter and are easy to lose:

- Absence must be *visible*. Before this, a missing ``statsmodels`` was
  indistinguishable from "the forecaster had nothing to say".
- The install must never be able to take the process down. It runs as a detached
  task, waits for memory headroom, and fails open everywhere.
"""

import asyncio

import pytest

from app.services import optional_deps
from app.services.optional_deps import (
    OptionalDep,
    install_missing,
    log_status,
    missing_optional_report,
    probe,
    wait_for_memory_headroom,
)


class TestRegistry:
    def test_registry_is_not_empty(self):
        assert optional_deps.OPTIONAL_DEPS, "soft tier must not be empty"

    def test_pandas_is_not_in_the_soft_tier(self):
        """pandas is imported unguarded by 457 files, so it cannot be optional.

        Treating it as soft would mean the app boots and then dies on the first
        factor sweep, which runs 300s after startup by default. This test exists so
        that a future "let's make installs fully optional" change fails loudly
        instead of quietly reintroducing the crash.
        """
        assert "pandas" not in {dep.module for dep in optional_deps.OPTIONAL_DEPS}

    def test_every_entry_declares_a_consequence(self):
        for dep in optional_deps.OPTIONAL_DEPS:
            assert dep.consequence.strip(), f"{dep.module} must state what breaks without it"
            assert dep.requirement.strip(), f"{dep.module} must state its requirement"
            assert dep.probe.strip(), f"{dep.module} must state how to probe it"


class TestProbe:
    def test_probe_reports_a_bool_per_dep(self):
        result = probe()
        assert set(result) == {dep.module for dep in optional_deps.OPTIONAL_DEPS}
        assert all(isinstance(v, bool) for v in result.values())

    def test_probe_matches_the_registry(self):
        assert list(probe()) == [dep.module for dep in optional_deps.OPTIONAL_DEPS]

    def test_absent_report_only_lists_absent_modules(self):
        present = probe()
        for module in missing_optional_report():
            assert present[module] is False, f"{module} is importable but reported absent"

    def test_absent_report_is_empty_when_everything_is_present(self, monkeypatch):
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: True)
        assert missing_optional_report() == {}

    def test_log_status_does_not_raise(self, caplog):
        log_status()  # exercised for not raising; content is log-format only


class TestMemoryGate:
    async def test_passes_immediately_with_headroom_to_spare(self):
        assert await wait_for_memory_headroom(
            container_memory_mb=10_000.0, required_headroom_mb=1_000.0, timeout=1.0
        ) is True

    async def test_fails_open_when_the_limit_is_never_met(self):
        """A gate that can never be satisfied must give up, not hang forever.

        Hanging would keep a background task alive indefinitely and, on Render,
        delay shutdown until SIGKILL.
        """
        result = await wait_for_memory_headroom(
            container_memory_mb=10.0,
            required_headroom_mb=10_000.0,
            timeout=1.0,
            poll_interval=0.1,
        )
        assert result is False

    async def test_polls_repeatedly_before_giving_up(self, monkeypatch):
        """Waiting must actually wait, not spin or exit on the first reading."""
        readings = iter([900.0, 900.0, 10.0])
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: True)

        import psutil

        class FakeProc:
            def memory_info(self):
                class Info:
                    rss = next(readings) * 1e6

                return Info()

        monkeypatch.setattr(psutil, "Process", lambda: FakeProc())
        assert await wait_for_memory_headroom(
            container_memory_mb=1_000.0,
            required_headroom_mb=100.0,
            timeout=5.0,
            poll_interval=0.01,
        ) is True

    async def test_missing_psutil_fails_open(self, monkeypatch):
        """If RSS cannot be read, install anyway rather than never installing."""
        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def fake_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("no psutil")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        assert await wait_for_memory_headroom(
            container_memory_mb=10.0, required_headroom_mb=10_000.0, timeout=1.0
        ) is True


class TestInstallMissing:
    async def test_no_op_when_everything_is_present(self, monkeypatch):
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: True)
        assert await install_missing() == [dep.module for dep in optional_deps.OPTIONAL_DEPS]

    async def test_returns_only_modules_that_became_importable(self, monkeypatch):
        """A package that fails to install must be absent from the result, not guessed.

        `_importable` stays False throughout, so even though pip "succeeds" nothing
        counts as installed.
        """
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: False)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_process)
        assert await install_missing(timeout=1.0) == []

    async def test_survives_a_pip_launch_failure(self, monkeypatch):
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: False)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _raises_oserror)
        assert await install_missing(timeout=1.0) == []

    async def test_one_failure_does_not_mask_the_others(self, monkeypatch):
        """Each package is installed independently, so a failing pip cannot skip the rest."""
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: False)
        seen = []

        async def _record(*args, **kwargs):
            seen.append(args[-1])
            return await _fake_process()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", _record)
        assert await install_missing(timeout=1.0) == []
        assert len(seen) == len(optional_deps.OPTIONAL_DEPS), (
            "every absent package must be attempted independently"
        )


async def _fake_process(*args, **kwargs):
    """A subprocess that runs, exits non-zero, and installs nothing."""

    class _Proc:
        returncode = 1

        async def communicate(self):
            return b"", b"pip: could not find a version"

        def kill(self):
            return None

        async def wait(self):
            return 1

    return _Proc()


async def _raises_oserror(*args, **kwargs):
    raise OSError("no subprocess support")


class TestBootWiring:
    def test_deferred_task_is_started_when_auto_install_is_on(self):
        """The task is started by the lifespan, and it must be cancellable."""
        from app.services import boot

        assert hasattr(boot, "start_deferred_deps")
        assert hasattr(boot, "stop_deferred_deps")
        assert boot.DEPS_TASK is None or isinstance(boot.DEPS_TASK, asyncio.Task)

    async def test_stop_is_safe_when_never_started(self):
        from app.services import boot

        boot.DEPS_TASK = None
        await boot.stop_deferred_deps()  # must not raise

    async def test_stop_cancels_a_running_task(self):
        from app.services import boot

        async def _forever():
            await asyncio.sleep(3600)

        boot.start_deferred_deps(_forever)
        task = boot.DEPS_TASK
        assert task is not None and not task.done()
        await boot.stop_deferred_deps()
        assert task.cancelled() or task.done()
        assert boot.DEPS_TASK is None

    async def test_task_failure_does_not_escape(self):
        """A raising factory is caught and logged by runner(), so the task completes clean.

        The guarantee is that nothing propagates. The task ends with result=None
        rather than an exception, which is what keeps a failed install invisible to
        the rest of the process.
        """
        from app.services import boot

        async def _raises():
            raise RuntimeError("installer exploded")

        boot.start_deferred_deps(_raises)
        task = boot.DEPS_TASK
        await asyncio.sleep(0.05)
        assert task.done()
        assert task.exception() is None, "runner() must absorb the failure"
        await boot.stop_deferred_deps()


class TestConfig:
    def test_auto_install_defaults_on(self):
        """Read the field default, not the live instance.

        conftest forces OPTIONAL_DEPS_AUTO_INSTALL off for every test so nothing
        reaches the network during a run; asserting on the instance would just be
        asserting the fixture.
        """
        from app.config import Settings

        assert Settings.model_fields["OPTIONAL_DEPS_AUTO_INSTALL"].default is True

    def test_memory_budget_is_anchored_to_render_free(self):
        """The gate must reflect the instance it runs on.

        Render free gives 512 MB. If that changes, these defaults are wrong, and
        failing here is how we find out before an install is OOM-killed in
        production.
        """
        from app.config import Settings

        container = Settings.model_fields["OPTIONAL_DEPS_CONTAINER_MEMORY_MB"].default
        headroom = Settings.model_fields["OPTIONAL_DEPS_INSTALL_HEADROOM_MB"].default

        assert container == 512.0, "Render free tier memory changed; re-derive this"
        assert 0 < headroom < container / 2, (
            "the headroom pip needs must be satisfiable against a near-empty "
            f"instance, and was {headroom} against {container}"
        )

    def test_headroom_fits_realistic_boot_footprint(self):
        """Boot measures ~315 MB, so the gate must still open at that footprint.

        A gate that never opens is indistinguishable from a disabled one: the
        install would silently never run and nothing would say so until a capability
        was missing. This is the assertion that keeps the gate honest in both
        directions - it must not block forever at the footprint we actually ship.
        """
        from app.config import Settings

        container = Settings.model_fields["OPTIONAL_DEPS_CONTAINER_MEMORY_MB"].default
        headroom = Settings.model_fields["OPTIONAL_DEPS_INSTALL_HEADROOM_MB"].default
        measured_boot_rss_mb = 315.0

        assert container - measured_boot_rss_mb >= headroom, (
            f"at the measured boot footprint of {measured_boot_rss_mb} MB there is "
            f"{container - measured_boot_rss_mb:.0f} MB free, less than the "
            f"{headroom} MB the install needs: the gate would never open"
        )

    def test_memory_wait_is_bounded(self):
        """An unbounded gate would hold a background task open indefinitely."""
        from app.config import Settings

        assert 0 < Settings.model_fields["OPTIONAL_DEPS_MEMORY_TIMEOUT_SECONDS"].default <= 900.0


class TestHealthEndpoint:
    """`/health` is what Render and UptimeRobot poll.

    It used to answer 200 even with a dead database, putting an instance that
    cannot reach its database into rotation. Both the status code and the exception
    detail are load-bearing, so both are pinned here.
    """

    async def _get(self, app):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/api/v1/health")

    async def test_healthy_database_answers_200(self, booted_app):
        response = await self._get(booted_app)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_dead_database_answers_503(self, booted_app, monkeypatch):
        """A process that cannot reach its database cannot serve trades."""
        from app import database

        class _Broken:
            def connect(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(database, "engine", _Broken())
        response = await self._get(booted_app)
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    async def test_detail_does_not_leak_the_exception_message(self, booted_app, monkeypatch):
        """The path is unauthenticated, and a DSN can appear in a driver message."""
        from app import database

        class _Broken:
            def connect(self):
                raise RuntimeError(
                    "connection to postgresql://user:hunter2@db.internal/jasper failed"
                )

        monkeypatch.setattr(database, "engine", _Broken())
        response = await self._get(booted_app)
        detail = response.json()["database"]["detail"]
        assert "hunter2" not in detail
        assert "postgresql://" not in detail
        assert detail == "RuntimeError"

    async def test_absent_optional_deps_are_reported(self, booted_app, monkeypatch):
        """Absence must be visible, or a degraded capability is indistinguishable
        from one that simply had nothing to report."""
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: False)
        body = (await self._get(booted_app)).json()
        absent = body["optional_dependencies_absent"]
        assert set(absent) == {dep.module for dep in optional_deps.OPTIONAL_DEPS}
        # Absence is reported but must not fail readiness.
        assert all(consequence.strip() for consequence in absent.values())

    async def test_absent_optional_deps_do_not_fail_readiness(self, booted_app, monkeypatch):
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: False)
        response = await self._get(booted_app)
        assert response.status_code == 200, (
            "a missing forecasting library must not take the instance out of rotation"
        )

    async def test_field_is_omitted_when_all_present(self, booted_app, monkeypatch):
        monkeypatch.setattr(optional_deps, "_importable", lambda probe: True)
        body = (await self._get(booted_app)).json()
        assert "optional_dependencies_absent" not in body