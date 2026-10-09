"""Boot and shutdown primitives for the API process.

Render's free tier is the constraint this exists for. A free instance has 512 MB
and sleeps after 15 minutes of inactivity, destroying the container. That makes
every wake a cold start, and a cold start has to finish before the service
answers. Three things go wrong without help:

1. **One slow dependency stalls the whole boot.** Broker connect, market-data
   WebSockets, Telegram polling, and forex polling all call third-party APIs. Any
   of them can hang for its full timeout. Several in series can exceed Render's
   startup window, so the deploy fails and the container is killed mid-boot, then
   retried, then killed again: a restart loop that looks like a deploy problem.

2. **A failure in one optional subsystem took down boot entirely.** Market data
   unavailable is not a reason to refuse to serve a health check. Anything that
   can degrade is isolated so it can fail on its own.

3. **Shutdown skipped its remaining steps after the first error.** Render sends
   SIGTERM and then force-kills. If `market_data_service.stop()` raised, the
   scheduler was never stopped and the database was never closed, leaving dirty
   state behind.

The split between *required* and *warm-up* matters most. Required work runs before
the app starts serving, because serving a request that cannot reach the database
or the agents would be worse than not serving at all. Warm-up work - WebSockets,
polling bots, listeners - starts immediately afterwards, in the background, and is
allowed to still be starting when the first request arrives. That is what makes a
cold container answer its health check in seconds rather than minutes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, List, Optional

logger = logging.getLogger(__name__)

#: Hard ceiling for any single boot step.
#:
#: Sized against Render's free-tier behaviour: the container is expected to be
#: listening promptly, and a step that has not finished in this long is not going
#: to. Failing fast and continuing is better than holding the process open, which
#: gets it killed.
STARTUP_STEP_TIMEOUT_SECONDS = 45.0

#: Total budget for background warm-up. Individual steps are already bounded; this
#: stops the warm-up task itself from lingering indefinitely.
WARMUP_BUDGET_SECONDS = 180.0

#: Background task started during lifespan, so shutdown can cancel it.
WARMUP_TASK: Optional["asyncio.Task"] = None

#: Deferred optional-dependency install. Separate from WARMUP_TASK because it runs
#: long after warm-up finishes - it waits out a settle period and then waits for
#: memory headroom, which on a busy instance can be minutes - and shutdown must be
#: able to cancel the wait without waiting it out.
DEPS_TASK: Optional["asyncio.Task"] = None


def log_boot(stage: str, detail: str, *, elapsed: Optional[float] = None) -> None:
    """One consistently formatted boot line.

    Boot is the only thing an operator sees when a deploy goes wrong, so it is
    logged in a fixed shape rather than free-form per call site.
    """
    suffix = f" in {elapsed:.1f}s" if elapsed is not None else ""
    logger.info("boot.%s: %s%s", stage, detail, suffix)


async def run_boot_step(
    name: str,
    factory: Callable[[], Awaitable[Any]],
    *,
    required: bool = False,
    timeout: float = STARTUP_STEP_TIMEOUT_SECONDS,
) -> Any:
    """Run one boot step under a timeout, isolating its failure.

    `required=True` re-raises, and is for steps without which the process cannot
    honestly serve traffic - the database, and agent registration. Everything else
    logs and returns None: a missing Telegram token or an unreachable exchange
    must not prevent the service from starting.

    The timeout is the important part. `asyncio.wait_for` cancels the coroutine on
    expiry, so a hung socket is abandoned rather than left to hold the process.
    """
    started = asyncio.get_running_loop().time()
    try:
        result = await asyncio.wait_for(factory(), timeout=timeout)
    except asyncio.TimeoutError:
        elapsed = asyncio.get_running_loop().time() - started
        if required:
            logger.error(
                "boot.%s: TIMED OUT after %.1fs (required)", name, elapsed
            )
            raise
        logger.warning(
            "boot.%s: timed out after %.1fs; continuing without it", name, elapsed
        )
        return None
    except asyncio.CancelledError:
        # Shutdown. Not a failure, and must not be swallowed.
        raise
    except Exception as exc:  # noqa: BLE001
        elapsed = asyncio.get_running_loop().time() - started
        if required:
            logger.error("boot.%s: FAILED after %.1fs: %s", name, elapsed, exc)
            raise
        logger.warning("boot.%s: failed after %.1fs: %s", name, elapsed, exc)
        return None

    elapsed = asyncio.get_running_loop().time() - started
    log_boot(name, "ok", elapsed=elapsed)
    return result


async def run_warmup(
    steps: List[tuple],
    *,
    budget: float = WARMUP_BUDGET_SECONDS,
) -> None:
    """Run optional subsystems in the background, after the app can serve.

    `steps` is a list of `(name, factory)` pairs, matching `run_boot_step` with
    `required=False`.

    Steps run in order but each is individually bounded, so one slow subsystem
    delays only itself. The whole pass is bounded too: on a cold container the
    goal is to have the essential trading path up first, not to have every
    optional integration ready before the first request.
    """
    global WARMUP_TASK

    async def runner() -> None:
        async with asyncio.timeout(budget):
            for name, factory in steps:
                try:
                    await run_boot_step(name, factory, required=False)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    # run_boot_step already logs; this is the outer safety net for
                    # a step that raises during setup rather than during await.
                    logger.warning("boot.warmup: %s could not start: %s", name, exc)

    WARMUP_TASK = asyncio.create_task(runner(), name="boot-warmup")

    def _done(task: "asyncio.Task") -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("boot.warmup: ended with error: %s", exc)
        else:
            logger.info("boot.warmup: all subsystems started")

    WARMUP_TASK.add_done_callback(_done)


async def stop_warmup() -> None:
    """Cancel the warm-up task if it is still running."""
    global WARMUP_TASK
    task = WARMUP_TASK
    WARMUP_TASK = None
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        # Cancellation is the expected outcome; a subsystem error during teardown
        # is not worth failing shutdown over.
        pass


def start_deferred_deps(factory: Callable[[], Awaitable[Any]]) -> None:
    """Start the deferred optional-dependency install as a cancellable task.

    Starts the task before the lifespan yields, but the task itself waits out a
    settle period and a memory gate before doing any work - so nothing actually
    happens until the app is serving and boot has stopped competing for memory.
    """
    global DEPS_TASK

    async def runner() -> None:
        try:
            await factory()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("boot.optional-deps: install aborted: %s", exc)

    DEPS_TASK = asyncio.create_task(runner(), name="boot-optional-deps")

    def _done(task: "asyncio.Task") -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("boot.optional-deps: ended with error: %s", exc)
        else:
            logger.info("boot.optional-deps: deferred install finished")

    DEPS_TASK.add_done_callback(_done)


async def stop_deferred_deps() -> None:
    """Cancel the deferred install if it is still running."""
    global DEPS_TASK
    task = DEPS_TASK
    DEPS_TASK = None
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        # Cancelling a waiting install is the normal path on shutdown.
        pass


async def shutdown_step(name: str, factory: Callable[[], Awaitable[Any]]) -> None:
    """Run one shutdown step, never raising.

    Render sends SIGTERM and then force-kills after a grace period. If an early
    step raised, everything after it would be skipped - so the scheduler would
    keep running, or the database would never be closed. Shutdown runs
    unconditionally through here instead, and a step that fails is logged and the
    next one still runs.
    """
    try:
        await asyncio.wait_for(factory(), timeout=20.0)
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.warning("shutdown.%s: timed out; continuing", name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("shutdown.%s: failed: %s", name, exc)
    else:
        logger.info("shutdown.%s: ok", name)