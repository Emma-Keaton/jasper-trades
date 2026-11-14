#!/usr/bin/env python3
"""
Jasper Kronos — Unified Launcher (Local + Cloud)

Launches the Kronos forecast service either locally or on Modal cloud.
The service connects to the jasper-trades backend for predictions.

Usage:
    # Local development (2GB RAM laptop)
    python launch_kronos.py --local

    # Cloud deployment (Modal)
    python launch_kronos.py --cloud

Environment variables (from .env):
    KRONOS_SERVICE_URL   # Local: http://localhost:8001 / Cloud: Modal URL
    KRONOS_API_KEY       # Required shared secret
    KRONOS_MODEL         # NeoQuasar/Kronos-mini (default, fits 2GB RAM)
    KRONOS_LOCAL_PORT    # 8001 (default for local mode)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

KRONOS_DIR = Path(__file__).resolve().parent


def load_env() -> None:
    """Load .env if present, without overwriting existing env vars."""
    env_file = KRONOS_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def run_local() -> None:
    """Start the local Kronos service on http://localhost:$KRONOS_LOCAL_PORT."""
    load_env()
    port = os.getenv("KRONOS_LOCAL_PORT", "8001")
    os.environ["KRONOS_SERVICE_URL"] = f"http://localhost:{port}"
    print(f"[kronos] Starting local service on http://localhost:{port}")
    print(f"[kronos] Model: {os.getenv('KRONOS_MODEL', 'NeoQuasar/Kronos-mini')}")
    print(f"[kronos] API key configured: {bool(os.getenv('KRONOS_API_KEY'))}")
    print()

    subprocess.run([sys.executable, str(KRONOS_DIR / "start_kronos.py")], check=True)


def run_cloud() -> None:
    """Deploy the Kronos service to Modal cloud."""
    load_env()
    api_key = os.getenv("KRONOS_API_KEY", "")
    if not api_key:
        print("[kronos] ERROR: KRONOS_API_KEY is required for cloud deployment.")
        print("[kronos]   Generate one: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("[kronos]   Then set it in .env or export KRONOS_API_KEY=<key>")
        sys.exit(1)

    # Set the Modal secret if not already set
    result = subprocess.run(
        ["modal", "secret", "list", "--format", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("[kronos] ERROR: Modal CLI not authenticated. Run: modal token set")
        sys.exit(1)

    print("[kronos] Deploying to Modal cloud...")
    print(f"[kronos] Model: {os.getenv('KRONOS_MODEL', 'NeoQuasar/Kronos-mini')}")
    subprocess.run(
        ["modal", "deploy", str(KRONOS_DIR / "modal_app.py")],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Jasper Kronos — Local + Cloud Launcher")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true", help="Run locally on localhost")
    group.add_argument("--cloud", action="store_true", help="Deploy to Modal cloud")
    args = parser.parse_args()

    if args.local:
        run_local()
    elif args.cloud:
        run_cloud()


if __name__ == "__main__":
    main()