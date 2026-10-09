"""Emit jasper-trades' single, authoritative, rerunnable schema.

`app.models` is declarative-only with no config or database import, so the
metadata can be read directly. That makes this genuinely generated rather than
hand-maintained, which matters: a hand-written copy drifts from the models and
the next `create_all` then disagrees with what the database actually has.

This replaces three files that had drifted apart:

  * `reset_db_p10k.sql`        - SQLite-flavoured DROP-everything reset
  * `reset_db_supabase.sql`    - the Postgres version of the same thing
  * `rerunnable_schema.sql`    - generated, but with no seeds and no
                                 incremental-column backfill

The two reset scripts were near-duplicates that had already diverged by 626
lines, and neither contained `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so
neither brought an *existing* database up to date: they only ever worked on an
empty one, destructively.

Output is PostgreSQL DDL for Supabase, safe to apply repeatedly.
"""

import os
import sys
import types
import uuid
from datetime import datetime

# models.py imports only sqlalchemy and stdlib, but the `app` package's
# __init__ may pull in config. Import the module by path to avoid that.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib.util  # noqa: E402


def load_models():
    """Import every declarative model in isolation, without executing app/__init__.py.

    `app/models_ext/` registers nine more tables on the same `Base` - broker
    connections, crypto credentials, cTrader accounts/execution logs/token
    refresh logs, and four Polymarket tables. Loading only `app/models.py`
    silently omitted all nine, so a database provisioned from the old
    `rerunnable_schema.sql` was missing them and every cTrader, Polymarket and
    broker-connection request failed with "relation does not exist". The count
    is asserted in the test suite so this cannot regress silently again.
    """
    from sqlalchemy.orm import declarative_base

    package = types.ModuleType("app")
    package.__path__ = [os.path.join(BACKEND_ROOT, "app")]
    sys.modules.setdefault("app", package)

    # models_ext modules are imported by their package path so they resolve the
    # same `app` package rather than creating a second copy of the metadata.
    ext_package = types.ModuleType("app.models_ext")
    ext_package.__path__ = [os.path.join(BACKEND_ROOT, "app", "models_ext")]
    sys.modules.setdefault("app.models_ext", ext_package)

    spec = importlib.util.spec_from_file_location(
        "app.models", os.path.join(BACKEND_ROOT, "app", "models.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.models"] = module
    spec.loader.exec_module(module)

    for name in (
        "crypto_credentials",
        "broker_connections",
        "ctrader",
        "polymarket",
    ):
        ext_spec = importlib.util.spec_from_file_location(
            f"app.models_ext.{name}",
            os.path.join(BACKEND_ROOT, "app", "models_ext", f"{name}.py"),
        )
        ext_module = importlib.util.module_from_spec(ext_spec)
        sys.modules[f"app.models_ext.{name}"] = ext_module
        ext_spec.loader.exec_module(ext_module)

    return module


# ---------------------------------------------------------------------------
# Backfill for pre-existing databases
# ---------------------------------------------------------------------------

# Columns added after a database was first provisioned. `CREATE TABLE IF NOT
# EXISTS` is a no-op against a table that already exists, so on an existing
# database these are the only statements that actually change anything. Without
# them an older deployment keeps the old shape and every new column raises
# "column does not exist" at runtime.
#
# Kept in step with the incremental lists in `app/migrations.py`, which is what
# runs at application startup. This file exists so an operator can reach the same
# state with the SQL editor and no deploy.
BACKFILL: dict[str, list[tuple[str, str]]] = {
    "device_settings": [
        ("payout_wallet_keys", "TEXT"),
        ("payout_config", "TEXT"),
        ("trove_api_key", "TEXT"),
        ("trove_base_url", "TEXT"),
        ("trove_enabled", "BOOLEAN"),
        ("trove_account_id", "TEXT"),
        ("trove_sandbox", "BOOLEAN DEFAULT true"),
        ("tiger_id", "TEXT"),
        ("tiger_api_key", "TEXT"),
        ("tiger_private_key", "TEXT"),
        ("tiger_enabled", "BOOLEAN"),
        ("akshare_config", "TEXT"),
        ("akshare_sandbox", "BOOLEAN DEFAULT true"),
        ("ctrader_sandbox", "BOOLEAN DEFAULT true"),
        ("default_currency", "TEXT DEFAULT 'USD'"),
        ("currency_conversion_enabled", "BOOLEAN DEFAULT true"),
        ("naira_bank_details", "TEXT"),
        ("solana_rpc_url", "TEXT"),
        ("jupiter_enabled", "BOOLEAN"),
        ("environment_mode", "TEXT DEFAULT 'sandbox'"),
        ("broker_paper_trading_config", "TEXT"),
        ("universal_paper_trading_config", "TEXT"),
        ("trading_mode", "TEXT DEFAULT 'practice'"),
        ("preferences", "TEXT"),
        ("groq_model", "TEXT"),
        ("groq_key", "TEXT"),
        ("default_brokers", "TEXT"),
        ("routing_mode", "TEXT"),
    ],
    "portfolios": [
        ("device_id", "VARCHAR(255) DEFAULT 'legacy_device'"),
        ("name", "VARCHAR(255) DEFAULT 'Default'"),
        ("cash", "FLOAT DEFAULT 10000.0"),
        ("initial_value", "FLOAT DEFAULT 10000.0"),
        ("initial_capital", "FLOAT DEFAULT 10000.0"),
        ("is_paper", "BOOLEAN DEFAULT true"),
        ("broker", "VARCHAR(64)"),
        ("is_active", "BOOLEAN DEFAULT true"),
    ],
    "signal_tips": [
        ("execution_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("execution_detail", "TEXT"),
        ("executed_at", "TIMESTAMP"),
    ],
    "trades": [
        ("portfolio_id", "INTEGER"),
        ("entry_price", "FLOAT"),
        ("exit_price", "FLOAT"),
        ("pnl", "FLOAT"),
        ("pnl_percent", "FLOAT"),
        ("error_detail", "TEXT"),
    ],
    "withdrawals": [
        # Required for every crypto payout. Without it the network has to be
        # guessed from the address, which cannot tell BSC from Ethereum.
        ("destination_chain", "VARCHAR(32)"),
        ("daily_pnl", "FLOAT"),
        ("payout_percentage", "FLOAT DEFAULT 50.0"),
        ("fee", "FLOAT DEFAULT 0.0"),
        ("net_amount", "FLOAT"),
    ],
    "signals": [
        ("metadata", "JSONB"),
    ],
}

#: Default paper-trading capital. Must match `PaperTradingService` and the
#: Portfolio column defaults; the previous reset scripts hard-coded this in
#: three places, which is how they drifted.
PAPER_CAPITAL = 10000.0

SEEDS = f"""
-- ============================================================
-- SEED: system paper portfolio and device settings
--
-- ON CONFLICT DO NOTHING keeps this re-runnable: applying the file to a live
-- database will not disturb an existing system portfolio.
-- ============================================================
INSERT INTO portfolios
    (device_id, name, cash, initial_value, initial_capital, is_paper, is_active)
VALUES
    ('__system__', 'System Paper Portfolio', {PAPER_CAPITAL}, {PAPER_CAPITAL}, {PAPER_CAPITAL}, true, true)
ON CONFLICT DO NOTHING;

INSERT INTO device_settings (device_id, trading_mode, environment_mode, universal_paper_trading_config)
VALUES ('__system__', 'practice', 'sandbox',
        '{{"enabled": true, "initial_capital": {PAPER_CAPITAL}, "current_balance": {PAPER_CAPITAL}, "total_pnl": 0.0, "currency": "USD"}}')
ON CONFLICT (device_id) DO NOTHING;
"""


def render_backfill() -> str:
    """`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for pre-existing databases."""
    lines = [
        "\n-- ============================================================",
        "-- BACKFILL: columns added after a database was first provisioned",
        "--",
        "-- CREATE TABLE IF NOT EXISTS is a no-op on a table that already exists,",
        "-- so on an existing database these are the statements that do the work.",
        "-- Harmless on a fresh one.",
        "-- ============================================================",
        "",
    ]
    for table in sorted(BACKFILL):
        lines.append(f"-- {table}")
        for column, definition in BACKFILL[table]:
            lines.append(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {definition};'
            )
        lines.append("")
    return "\n".join(lines)


HEADER = """-- jasper-trades: complete database schema (Supabase / PostgreSQL)
--
-- Generated from app/models.py by scripts/generate_schema.py.
-- Do not hand-edit: regenerate with `python scripts/generate_schema.py`.
--
-- RE-RUNNABLE AND NON-DESTRUCTIVE. Every statement is guarded, so this file can
-- be applied to an empty project, a partially provisioned one, or a live one,
-- any number of times:
--   * empty project      -> CREATE TABLE builds the full schema, then seeds run
--   * existing project   -> tables are left alone, the backfill block adds any
--                           column added since, seeds are skipped on conflict
--   * repeated runs      -> no-ops
--
-- Apply in the Supabase SQL editor, or:
--   psql "$DATABASE_URL" -f backend/scripts/schema.sql
--
-- The application also reconciles the schema on startup (`app/migrations.py`:
-- create_all plus incremental column adds). This file exists so the same state
-- can be reached from the SQL editor with no deploy, which matters when the
-- first deploy cannot start because the schema is missing a column it needs.
--
-- To DROP everything and start over instead, run backend/scripts/reset.sh, which
-- drops the tables first and then applies this file. That is destructive and is
-- kept as a separate, explicit step so this file never destroys data by accident.

"""


def main() -> int:
    from emit_ddl import generate

    models = load_models()
    ddl = generate(models.Base.metadata)

    out = os.path.join(BACKEND_ROOT, "scripts", "schema.sql")
    body = HEADER + ddl + render_backfill() + SEEDS
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(body)

    print(f"wrote {out}")
    print(f"tables: {len(models.Base.metadata.tables)}")
    print(
        "backfill columns: "
        f"{sum(len(c) for c in BACKFILL.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())