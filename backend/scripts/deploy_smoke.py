#!/usr/bin/env python
"""Post-deploy smoke test — run right after every local/cloud deploy.

Checks the whole automated pipeline is alive:
  /api/v1/health, /api/v1/system/status, /api/v1/system/pipeline-status,
  /api/v1/settings/env-status, /api/v1/auto-trading/status

Usage:
  python scripts/deploy_smoke.py [base_url]   # default http://localhost:8000

Exit code 0 = all good, 1 = something is broken (prints what failed).
"""
from __future__ import annotations

import os
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")).rstrip("/")
DEVICE = os.environ.get("SMOKE_DEVICE_ID", "")
TIMEOUT = 20.0


def main() -> int:
    headers = {"X-Device-ID": DEVICE} if DEVICE else {}
    failures = []

    def check(name: str, path: str, expect: int = 200, must: dict | None = None):
        try:
            r = httpx.get(BASE + path, headers=headers, timeout=TIMEOUT)
            ok = r.status_code == expect
            if ok and must:
                body = r.json()
                for key, val in must.items():
                    if body.get(key) != val:
                        ok = False
            print(f"[{'OK' if ok else 'FAIL'}] {name}: {path} -> {r.status_code}")
            if not ok:
                failures.append(name)
        except Exception as e:
            print(f"[FAIL] {name}: {path} -> {e}")
            failures.append(name)

    check("health", "/api/v1/health")
    check("system status", "/api/v1/system/status")
    check("pipeline status", "/api/v1/system/pipeline-status")
    check("env status", "/api/v1/settings/env-status")
    check("auto executor status", "/api/v1/auto-trading/status")
    check("brokers", "/api/v1/brokers/accounts")
    check("llm providers", "/api/v1/llm/key-status", must=None) if DEVICE else None
    if DEVICE:
        check("llm key-status (device)", "/api/v1/llm/key-status")
        check("whale status (device)", "/api/v1/solana/whales/status")
        check("strategy suite (device)", "/api/v1/strategy-suite/status")

    # Pipeline status should show the scheduler running with our new tasks.
    try:
        r = httpx.get(BASE + "/api/v1/system/pipeline-status", headers=headers, timeout=TIMEOUT)
        body = r.json()
        tasks = (body.get("scheduler") or {}).get("tasks") or {}
        for required in ("strategy_evolve", "whale_fallback", "score_kronos", "refit_learned", "poll_signal_sources"):
            if required not in tasks:
                print(f"[FAIL] scheduler missing task: {required}")
                failures.append(f"task:{required}")
            else:
                print(f"[OK] scheduler task present: {required}")
    except Exception as e:
        print(f"[FAIL] pipeline-status parse: {e}")
        failures.append("pipeline-status")

    print()
    if failures:
        print(f"SMOKE FAILED ({len(failures)}): {failures}")
        return 1
    print("SMOKE OK — pipeline healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
