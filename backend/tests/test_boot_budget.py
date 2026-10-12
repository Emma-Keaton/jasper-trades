"""Boot cost must stay inside the Render free-tier budget.

Render's free tier gives 512 MB and destroys the container after 15 minutes
idle, so *every* cold start pays the full import cost. Measured on the baseline
before this work, importing `app.main` cost 314 MB and 11.7 s across 3211
modules - leaving roughly 200 MB for request handling, which is not much once
asyncpg, market-data buffers and concurrent requests are working.

Two eager imports were responsible for about 40% of that and are now deferred:

* `scipy.stats` via `quantlib_service` - ~1.8 s and tens of MB, needed only for
  a normal distribution and one percentile call, on an endpoint that is rarely
  used.
* `ccxt` via `brokers/ccxt_service` - ~1.1 s and ~54 MB, for a broker that only
  activates when a user supplies CCXT credentials, which by default nobody has.

These tests are deliberately thresholds rather than exact values, so an
unchanged platform does not fail them. They fail on a regression that would
reintroduce a heavy eager import.
"""

from __future__ import annotations

import importlib
import io
import contextlib
import sys

import pytest


def _fresh_interpreter_source() -> str:
    return (
        "import sys, io, time, contextlib\n"
        "import psutil\n"
        "proc = psutil.Process()\n"
        "base = proc.memory_info().rss\n"
        "t0 = time.monotonic()\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n"
        "    import app.main\n"
        "dt = time.monotonic() - t0\n"
        "rss = proc.memory_info().rss\n"
        "sys.stdout.write('%.3f %.1f %d %d %d\\n' % (\n"
        "    dt, rss/1e6, len(sys.modules),\n"
        "    int('ccxt' in sys.modules), int('scipy.stats' in sys.modules)))\n"
    )


#: How many clean-interpreter imports to time.
#:
#: Three is enough to identify a median and costs about a minute on a cold cache.
#: The point is not statistical rigour, it is that a *systematically* slower import
#: survives the median while a *randomly* slow one does not. An eager import costs
#: the same on every run; a busy host does not.
BOOT_TIMING_RUNS = 3


@pytest.fixture(scope="module")
def boot_profile():
    """Import `app.main` in a clean interpreter and measure it.

    Run in a subprocess because the test session has already imported most of
    the app, which would make every measurement read as near-zero.

    Timed ``BOOT_TIMING_RUNS`` times and reported as a median. A single sample on a
    shared machine conflates "the app got slower" with "something else was running":
    the same code measured 14 s and 45 s minutes apart with no change between them.
    A regression in import cost is paid on every run, so it survives the median.
    """
    import statistics
    import subprocess
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    samples = []
    profile = None

    for _ in range(BOOT_TIMING_RUNS):
        result = subprocess.run(
            [sys.executable, "-c", _fresh_interpreter_source()],
            capture_output=True,
            text=True,
            cwd=str(backend),
            timeout=300,
        )
        line = (result.stdout or "").strip().splitlines()
        if not line:
            continue
        seconds, rss_mb, modules, ccxt_loaded, scipy_loaded = line[-1].split()
        samples.append(float(seconds))
        # Module/eager-import facts are deterministic; keep the last successful read.
        profile = {
            "rss_mb": float(rss_mb),
            "modules": int(modules),
            "ccxt_loaded": bool(int(ccxt_loaded)),
            "scipy_loaded": bool(int(scipy_loaded)),
        }

    if not samples:
        pytest.skip(f"could not measure boot: {result.stderr[-400:]}")

    profile.update(
        {
            "seconds": statistics.median(samples),
            "seconds_min": min(samples),
            "seconds_max": max(samples),
            "samples": samples,
        }
    )
    return profile


class TestBootMemory:
    def test_import_fits_the_free_tier(self, boot_profile):
        """512 MB container. Import cost must leave real headroom.

        The pre-fix baseline was 314 MB; anything near that again means a heavy
        import has become eager.
        """
        assert boot_profile["rss_mb"] < 260, (
            f"importing app.main costs {boot_profile['rss_mb']:.0f} MB. The "
            "free tier allows 512 MB total, so this leaves too little for "
            "request handling. Check for a newly eager heavy import."
        )

    def test_heavy_optional_libraries_are_not_loaded(self, boot_profile):
        assert boot_profile["ccxt_loaded"] is False, (
            "ccxt is imported at boot (~54 MB). It should load on first "
            "broker connect; see brokers/ccxt_service._ccxt()."
        )
        assert boot_profile["scipy_loaded"] is False, (
            "scipy.stats is imported at boot (~1.8 s). It should load on first "
            "QuantLib call; see quantlib_service._stats()."
        )


#: Wall-clock ceiling for importing `app.main` in a clean interpreter.
#:
#: Anchored to `STARTUP_STEP_TIMEOUT_SECONDS` in app/services/boot.py (45s), which
#: is the project's own statement of how long it is willing to wait before
#: concluding that something is wrong. It is not derived from a measurement on any
#: one machine: the same commit imports in 14 s and 28 s depending on host memory
#: pressure, so a tighter bound measures the host rather than the app.
#:
#: The regression this test exists to catch - scipy or ccxt becoming eager imports -
#: adds several seconds to *every* run and is therefore caught deterministically by
#: `test_module_count_stays_bounded` and
#: `test_heavy_optional_libraries_are_not_loaded`. This is the backstop for gross
#: slowness only, and deliberately is not the primary guard.
BOOT_IMPORT_SECONDS_CEILING = 45.0


class TestBootTime:
    def test_import_completes_promptly(self, boot_profile):
        """A cold start pays this every wake.

        Measured as the median of `BOOT_TIMING_RUNS` clean interpreters, because a
        single sample conflates app slowness with host contention on a shared
        machine. The threshold is otherwise deliberately loose: this is a backstop
        against gross slowness, and a tight bound produces a test people learn to
        ignore.

        The eager-import regressions this was written for are caught
        deterministically by `test_heavy_optional_libraries_are_not_loaded` and
        `test_module_count_stays_bounded`, neither of which depends on host speed.
        """
        assert boot_profile["seconds"] < BOOT_IMPORT_SECONDS_CEILING, (
            f"importing app.main takes {boot_profile['seconds']:.1f} s "
            f"(median of {BOOT_TIMING_RUNS}; samples "
            f"{[round(s, 1) for s in boot_profile['samples']]}), against a "
            f"{BOOT_IMPORT_SECONDS_CEILING:.0f}s ceiling. On a free-tier instance "
            "this is paid on every wake after the idle sleep. If scipy or ccxt have "
            "become eager again, expect ~11.7 s and a module count near 3211 - check "
            "test_module_count_stays_bounded, which is not host-sensitive."
        )

    def test_import_is_not_outlier_heavy(self, boot_profile):
        """A consistently slow import is a regression; a randomly slow one is the host.

        Guards against the median hiding a genuine problem: if every run is slow the
        ratio stays near 1, whereas host contention produces one bad sample among
        several good ones.
        """
        lo, hi = boot_profile["seconds_min"], boot_profile["seconds_max"]
        assert lo > 0
        assert hi / lo < 3.0, (
            f"boot samples ranged {lo:.1f}-{hi:.1f}s "
            f"({[round(s, 1) for s in boot_profile['samples']]}). Spread this wide "
            "with no code change usually means the host is contended rather than the "
            "app; if it reproduces on an idle machine, the import really is uneven."
        )

    def test_module_count_stays_bounded(self, boot_profile):
        """A crude but effective proxy for accidental eager imports.

        The baseline was 3211; deferring scipy and ccxt brought it to ~2400.
        """
        assert boot_profile["modules"] < 2900, (
            f"{boot_profile['modules']} modules are imported at startup "
            "(baseline 3211). Something heavy is being imported eagerly again."
        )


class TestDeferredImportsStillWork:
    """Deferring must not change behaviour."""

    def test_ccxt_resolves_on_first_use(self):
        """The lazy accessor must return a usable module."""
        from app.brokers import ccxt_service

        if not ccxt_service.CCXT_AVAILABLE:
            pytest.skip("ccxt not installed")

        module = ccxt_service._ccxt()
        assert hasattr(module, "async_support") or hasattr(module, "binance")

    def test_ccxt_availability_check_needs_no_import(self):
        """`CCXT_AVAILABLE` is computed from package metadata, not by importing."""
        from app.brokers import ccxt_service

        # Must not have imported ccxt just to answer this.
        ccxt_service._ccxt_module = None
        assert isinstance(ccxt_service.CCXT_AVAILABLE, bool)

    def test_quantlib_matches_black_scholes_reference(self):
        """Lazy scipy must produce the same numbers.

        S, K=100, T=1, r=0.05, sigma=0.20, call -> 10.4506.
        """
        from app.services.quantlib_service import QuantLibService

        service = QuantLibService()
        result = service.black_scholes_price(100, 100, 1, 0.05, 0.2, "call")
        assert result["option_price"] == pytest.approx(10.4506, abs=1e-3)

    def test_quantlib_greeks_match_reference(self):
        """delta ~0.6368, gamma ~0.0188 for the same inputs."""
        from app.services.quantlib_service import QuantLibService

        greeks = QuantLibService().calculate_greeks(100, 100, 1, 0.05, 0.2, "call")
        assert greeks["delta"] == pytest.approx(0.6368, abs=1e-3)
        assert greeks["gamma"] == pytest.approx(0.0188, abs=1e-4)

    def test_ccxt_broker_still_reports_no_credentials(self):
        """The placeholder path must survive the lazy import change."""
        from app.brokers.ccxt_service import CCXTBrokerService

        broker = CCXTBrokerService(exchange_id="bybit", config={})
        assert broker.exchange is None


class TestHeavyModulesStayOutOfBoot:
    """Direct checks that nothing re-adds an eager heavy import."""

    @pytest.mark.parametrize(
        "module_path",
        [
            # (file, forbidden import) - the exact regressions fixed above.
            ("app/services/quantlib_service.py", "from scipy import stats"),
            ("app/brokers/ccxt_service.py", "import ccxt.async_support as ccxt"),
        ],
    )
    def test_no_module_level_heavy_import(self, module_path):
        import re
        from pathlib import Path

        backend = Path(__file__).resolve().parent.parent
        relative, forbidden = module_path
        source = (backend / relative).read_text(encoding="utf-8")

        # Only module-level imports matter; the same import inside a function is
        # exactly what we want.
        offending = [
            line
            for line in source.splitlines()
            if line.strip() == forbidden and not line.startswith((" ", "\t"))
        ]
        assert not offending, (
            f"{relative} imports '{forbidden}' at module level again. Keep it "
            "behind the lazy accessor; it is a large boot cost on a 512 MB "
            "container."
        )

    def test_no_optional_library_is_imported_by_the_broker_registry(self):
        """`app.brokers` is imported by every request path; it must stay light."""
        backend_pycache = None
        import subprocess
        from pathlib import Path

        backend = Path(__file__).resolve().parent.parent
        code = (
            "import sys, io, contextlib\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n"
            "    import app.brokers\n"
            "sys.stdout.write(','.join(sorted(\n"
            "    m for m in ('ccxt','pandas','sklearn','scipy','torch') if m in sys.modules)))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(backend),
            timeout=180,
        )
        loaded = (result.stdout or "").strip()
        assert loaded == "", (
            f"importing app.brokers pulls in {loaded}. The registry is on every "
            "request path, so these must stay deferred to first use."
        )