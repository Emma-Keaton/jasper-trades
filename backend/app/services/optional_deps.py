"""Optional third-party dependencies: probing and, when explicitly enabled, install.

Two kinds of dependency get mixed up in this codebase, and only one of them can be
treated as optional:

**Hard dependencies** are imported at module scope with no guard. ``pandas`` is the
important one: 457 files import it unguarded, including the entire ``alpha_zoo``.
It is declared in ``requirements.txt`` and there is no way to make it soft without
rewriting every one of those imports. An absent ``pandas`` is a broken build, not a
degraded feature.

**Soft dependencies** are imported inside a function or a ``try`` block, and the
code around them already handles absence:

* ``statsmodels`` - ``app/services/forecasting/statsmodels.py:17-23`` sets
  ``_AVAILABLE = False`` and the deterministic numpy forecaster runs instead.
* ``yfinance`` - ``app/services/market_data_service.py:370-378`` is the documented
  last-resort price fallback and returns ``None`` on any failure.

Those degrade quietly, which is the problem. A missing package looks identical to
"the data source had nothing for you", so nobody can tell from the logs that a
capability is missing. ``probe()`` and :func:`missing_optional_report` exist to
make absence visible, and are surfaced on the health endpoint.

**On installing at runtime.** :func:`install_deferred` ``pip install``\\ s the soft
tier after the app is already serving, once the process is under
``OPTIONAL_DEPS_MAX_RSS_MB``. That ordering matters on Render's free tier, which
gives 512 MB and destroys the container after 15 idle minutes: boot and warm-up are
where memory peaks, and an install competing with them can be OOM-killed
mid-extraction and leave a half-written ``site-packages``.

Note the cost this accepts, since it is real: because the container is ephemeral,
a startup install re-downloads on **every** wake. ``requirements.txt`` is installed
once at build time and costs nothing per wake, so declaring these there is still
better where the build environment allows it. The difference is that the packages
are available at all rather than the app silently degrading, and absence is now
reported on ``/api/v1/health`` instead of being invisible.

Installation is fail-soft by design: a package that cannot be installed is logged
and the app continues without it, because that is the same state it is in now. The
one thing it must never do is raise.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionalDep:
    """One soft dependency, and what the app does without it."""

    module: str
    requirement: str
    #: Import path proving availability. Chosen over the top-level module because
    #: a package can be importable while the specific symbol used here is not -
    #: ``statsmodels`` installs cleanly but has no ``tsa.holtwinters`` on some
    #: builds, and importing the bare module would report a false positive.
    probe: str
    #: Human-readable consequence of absence, for the health endpoint.
    consequence: str


#: The soft tier. Anything imported unguarded at module scope does NOT belong here;
#: see the module docstring for why pandas is excluded despite being data-heavy.
OPTIONAL_DEPS: Tuple[OptionalDep, ...] = (
    OptionalDep(
        module="statsmodels",
        requirement="statsmodels>=0.14.0",
        probe="statsmodels.tsa.holtwinters",
        consequence=(
            "ETS/Holt-Winters forecasting disabled; the deterministic numpy "
            "forecaster is used instead"
        ),
    ),
    OptionalDep(
        module="yfinance",
        requirement="yfinance>=0.2.0",
        probe="yfinance",
        consequence=(
            "the last-resort equity price fallback is unavailable; symbols not "
            "covered by the primary market-data sources will have no price"
        ),
    ),
)


def _importable(probe: str) -> bool:
    """Whether ``probe`` can be imported, without importing its parent packages twice."""
    try:
        importlib.import_module(probe)
        return True
    except Exception:  # noqa: BLE001 - a broken optional dep is any import error
        return False


def probe() -> Dict[str, bool]:
    """Map each optional dependency to whether it is currently importable."""
    return {dep.module: _importable(dep.probe) for dep in OPTIONAL_DEPS}


def missing_optional_report() -> Dict[str, str]:
    """Consequence text for each absent soft dependency.

    Returned as ``{module: consequence}`` and only contains absent packages, so an
    empty dict means the optional tier is fully present.
    """
    return {
        dep.module: dep.consequence
        for dep in OPTIONAL_DEPS
        if not _importable(dep.probe)
    }


def log_status() -> None:
    """Log the soft tier's state once, so absence is never silent."""
    absent = missing_optional_report()
    if not absent:
        logger.info("optional-deps: all present (%s)", ", ".join(d.module for d in OPTIONAL_DEPS))
        return
    for module, consequence in absent.items():
        logger.warning("optional-deps: %s is not installed - %s", module, consequence)


async def install_missing(*, timeout: float = 180.0) -> List[str]:
    """``pip install`` any absent soft dependency, bounded and never raising.

    Runs the install in a subprocess rather than in-process so that a resolver
    failure, a network stall, or a compiler error cannot corrupt the running
    interpreter's import state. Returns the modules that ended up importable
    afterwards; a module that fails to install is simply absent from the result.

    Each package is installed on its own so one failure does not mask the others.

    The timeout is per package and has to be generous: measured on this machine,
    installing statsmodels and yfinance takes ~55s and ~109s respectively, so a
    short default silently reports "still unavailable" on a perfectly healthy
    network. This runs as a detached task rather than a boot step, so it is not
    competing with the 45s per-step boot ceiling.
    """
    absent = [dep for dep in OPTIONAL_DEPS if not _importable(dep.probe)]
    if not absent:
        logger.info("optional-deps: nothing to install")
        return [dep.module for dep in OPTIONAL_DEPS]

    logger.warning(
        "optional-deps: installing %d absent package(s) after startup: %s. "
        "Declaring these in requirements.txt would still be better: on Render's "
        "free tier the container is destroyed on every idle sleep, so this "
        "re-downloads on every wake.",
        len(absent),
        ", ".join(dep.module for dep in absent),
    )

    installed: List[str] = []
    for dep in absent:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                dep.requirement,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as exc:
            logger.warning("optional-deps: could not start pip for %s: %s", dep.module, exc)
            continue

        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("optional-deps: pip timed out after %.0fs for %s", timeout, dep.module)
            continue

        if _importable(dep.probe):
            installed.append(dep.module)
            logger.info("optional-deps: installed %s", dep.module)
        else:
            # pip's own output is deliberately not surfaced: it is long, and it can
            # echo index URLs. The module name is enough to act on.
            logger.warning(
                "optional-deps: %s still unavailable after install attempt (pip exit %s)",
                dep.module,
                proc.returncode,
            )

    return installed


async def wait_for_memory_headroom(
    *,
    max_rss_mb: float,
    timeout: float,
    poll_interval: float = 5.0,
) -> bool:
    """Wait until RSS is under ``max_rss_mb``. Returns False if it never got there.

    Render's free tier gives 512 MB total and destroys the container on idle sleep,
    so an install that starts while the process is already large can be OOM-killed
    mid-extraction and leave a half-written site-packages. Waiting for headroom is
    cheaper than recovering from that.

    Fails open on purpose: if RSS cannot be read at all, treat it as acceptable
    rather than blocking the install forever, and log that the gate was skipped.
    """
    try:
        import psutil
    except ImportError:
        logger.warning("optional-deps: psutil unavailable; skipping the memory gate")
        return True

    process = psutil.Process()
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            rss_mb = process.memory_info().rss / 1e6
        except Exception as exc:  # noqa: BLE001
            logger.warning("optional-deps: could not read RSS (%s); proceeding", exc)
            return True

        if rss_mb <= max_rss_mb:
            logger.info("optional-deps: memory headroom available (%.0f MB)", rss_mb)
            return True

        if asyncio.get_running_loop().time() >= deadline:
            logger.warning(
                "optional-deps: still %.0f MB after %.0fs (limit %.0f MB); proceeding anyway",
                rss_mb,
                timeout,
                max_rss_mb,
            )
            return False

        logger.info(
            "optional-deps: waiting for memory (%.0f MB > %.0f MB limit)", rss_mb, max_rss_mb
        )
        await asyncio.sleep(poll_interval)


async def install_deferred() -> List[str]:
    """Settle, wait for memory, then install the absent soft tier.

    The order is the point. Boot and warm-up both run before the app yields, and
    they are where memory peaks; installing then would compete with the part of
    startup that has to succeed. This waits for the app to be serving and quiet
    first.
    """
    from app.config import settings

    await asyncio.sleep(settings.OPTIONAL_DEPS_SETTLE_SECONDS)
    await wait_for_memory_headroom(
        max_rss_mb=settings.OPTIONAL_DEPS_MAX_RSS_MB,
        timeout=settings.OPTIONAL_DEPS_MEMORY_TIMEOUT_SECONDS,
    )
    return await install_missing()


async def ensure_optional_deps() -> Optional[List[str]]:
    """Status-only entry point: log what is absent and install nothing.

    Used where an install would be wrong - notably on the synchronous path. The
    deferred installer is :func:`install_deferred`.
    """
    log_status()
    return None