"""Drive the real app lifespan and watch the deferred optional-dep install.

Not a pytest test: this must boot the genuine lifespan (the one `booted_app` also
uses) with OPTIONAL_DEPS_AUTO_INSTALL left on, which conftest deliberately forces
off for the suite. That is the only way to prove the deferred path is actually
reachable in production and not just unit-tested.

Usage: python scripts/exercise_optional_deps.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Same bootstrap the other scripts use: this file lives in scripts/, but `app` has
# to be importable as a top-level package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set before importing config: pydantic reads the environment at import time.
os.environ.setdefault("OPTIONAL_DEPS_AUTO_INSTALL", "true")
os.environ.setdefault("OPTIONAL_DEPS_SETTLE_SECONDS", "3")

from app.config import settings  # noqa: E402
from app.services.boot import DEPS_TASK  # noqa: E402
from app.services.optional_deps import probe  # noqa: E402


def _rss_mb() -> float:
    import psutil

    return psutil.Process().memory_info().rss / 1e6


async def main() -> int:
    print(f"auto_install={settings.OPTIONAL_DEPS_AUTO_INSTALL} "
          f"settle={settings.OPTIONAL_DEPS_SETTLE_SECONDS}s "
          f"limit={settings.OPTIONAL_DEPS_MAX_RSS_MB}MB", file=sys.stderr)
    print(f"soft tier before boot: {probe()}", file=sys.stderr)

    from app.main import app

    started = time.monotonic()
    async with app.router.lifespan_context(app):
        elapsed = time.monotonic() - started
        print(f"lifespan entered after {elapsed:.1f}s, RSS {_rss_mb():.0f} MB", file=sys.stderr)
        print(f"soft tier while serving: {probe()}", file=sys.stderr)

        import app.services.boot as boot

        task = boot.DEPS_TASK
        if task is None:
            print("FAIL: DEPS_TASK was not started; install can never run", file=sys.stderr)
            return 1
        print("deferred task is running; waiting for it...", file=sys.stderr)

        try:
            # Generous: the settle window plus a real pip install.
            await asyncio.wait_for(asyncio.shield(task), timeout=420)
        except asyncio.TimeoutError:
            print("FAIL: deferred install did not finish in 420s", file=sys.stderr)
            return 1

    total = time.monotonic() - started
    print(f"lifespan exited after {total:.1f}s", file=sys.stderr)
    print(f"soft tier after: {probe()}", file=sys.stderr)

    from app.services.optional_deps import missing_optional_report

    absent = missing_optional_report()
    if absent:
        print(f"FAIL: still absent after install: {sorted(absent)}", file=sys.stderr)
        return 1

    print("PASS: deferred install ran and closed the gap", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
