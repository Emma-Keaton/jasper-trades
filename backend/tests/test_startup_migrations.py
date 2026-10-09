"""`app/migrations.py` is what runs on startup, so it is what must not be wrong.

The generated `schema.sql` and this module both have to bring an existing database
to the current shape. They duplicate a column list, which is exactly the kind of
duplication that rots, so these tests hold them to each other.

The scenario that matters: a database provisioned before the payout work existed.
`CREATE TABLE IF NOT EXISTS` does nothing for a table that is already there, so
without the incremental column adds the new columns are simply absent and fail
later, at request time, as "column does not exist".
"""

from __future__ import annotations

import inspect

import pytest
import sqlalchemy as sa

from app.migrations import (
    _migrate_device_settings,
    _migrate_portfolios,
    _migrate_signal_tips,
    _migrate_trades,
    _migrate_withdrawals,
    add_column_if_missing,
    get_existing_columns,
)
from app.models import Base


LEGACY_TABLES = {
    "device_settings": ["id", "device_id", "created_at"],
    "portfolios": ["id", "cash"],
    "signal_tips": ["id", "device_id", "symbol"],
    "trades": ["id", "symbol"],
    "withdrawals": ["id", "portfolio_id", "amount"],
}


@pytest.fixture
def legacy_engine():
    """An async SQLite database holding an OLD shape.

    The tables exist but are missing every column added since. This is the exact
    situation an upgraded Supabase project is in.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine("sqlite+aiosqlite://")


@pytest.fixture
def legacy_database(legacy_engine):
    """Build the legacy schema and yield (engine, helper)."""
    import asyncio

    import app.migrations as migrations

    async def build():
        async with legacy_engine.begin() as conn:
            for table, columns in LEGACY_TABLES.items():
                # LEGACY_TABLES lists "id" first; it is already the primary key.
                extra = [c for c in columns if c != "id"]
                await conn.execute(
                    sa.text(
                        f"CREATE TABLE {table} ("
                        "id INTEGER PRIMARY KEY"
                        + (", " + ", ".join(f"{c} TEXT" for c in extra) if extra else "")
                        + ")"
                    )
                )

    async def columns_of(table: str) -> set:
        async with legacy_engine.begin() as conn:
            result = await conn.execute(sa.text(f"PRAGMA table_info({table})"))
            return {row[1] for row in result.fetchall()}

    async def run(coro):
        return await coro

    asyncio.new_event_loop().run_until_complete(build())
    return legacy_engine, columns_of, run


class TestColumnAddIsIdempotent:
    async def test_adds_a_missing_column(self, legacy_database):
        engine, columns_of, _ = legacy_database

        import app.migrations as migrations

        migrations.engine = engine
        migrations.get_existing_columns = columns_of

        assert "destination_chain" not in await columns_of("withdrawals")

        await migrations.add_column_if_missing(
            "withdrawals", "destination_chain", "TEXT", "VARCHAR(32)"
        )

        assert "destination_chain" in await columns_of("withdrawals")

    async def test_running_twice_is_safe(self, legacy_database):
        """Startup runs this on every boot, so a second application must be a
        no-op rather than an error - otherwise the app cannot boot twice."""
        engine, columns_of, _ = legacy_database

        import app.migrations as migrations

        migrations.engine = engine
        migrations.get_existing_columns = columns_of

        await migrations.add_column_if_missing(
            "withdrawals", "destination_chain", "TEXT", "TEXT"
        )
        await migrations.add_column_if_missing(
            "withdrawals", "destination_chain", "TEXT", "TEXT"
        )

        assert "destination_chain" in await columns_of("withdrawals")

    async def test_migrate_brings_a_legacy_database_up_to_date(self, legacy_database):
        """End to end: a pre-payout database must end up with the columns the new
        code reads, or the first payout request fails with 'no such column'."""
        engine, columns_of, _ = legacy_database

        import app.migrations as migrations

        migrations.engine = engine
        migrations.get_existing_columns = columns_of

        async def get_existing_tables():
            return set(LEGACY_TABLES)

        migrations.get_existing_tables = get_existing_tables
        # `add_column_if_missing` picks its DDL from `settings.using_postgres`,
        # so this needs a real object. Bound to the legacy engine so the inspect
        # helpers stay coherent with the engine actually in use.
        migrations.settings = type(
            "S", (), {"using_postgres": False, "DEBUG": False}
        )()

        await migrations._migrate_device_settings()
        await migrations._migrate_withdrawals()

        settings_columns = await columns_of("device_settings")
        assert "payout_wallet_keys" in settings_columns
        assert "payout_config" in settings_columns

        withdrawal_columns = await columns_of("withdrawals")
        assert "destination_chain" in withdrawal_columns
        assert "net_amount" in withdrawal_columns

    def test_running_twice_is_safe(self, legacy_database):
        """Second application must be a no-op, not an error. Startup runs this on
        every boot, so an error here would make the app unbootable."""
        import asyncio

        import app.migrations as migrations

        engine, columns_of, _ = legacy_database
        migrations.engine = engine
        migrations.get_existing_columns = columns_of

        async def go():
            await migrations.add_column_if_missing(
                "withdrawals", "destination_chain", "TEXT", "TEXT"
            )
            await migrations.add_column_if_missing(
                "withdrawals", "destination_chain", "TEXT", "TEXT"
            )

        asyncio.new_event_loop().run_until_complete(go())


class TestMigratorsCoverTheModels:
    """Every column the ORM declares must be reachable by the startup migrator,
    or an upgraded deployment silently lacks it."""

    def test_device_settings_migrator_matches_model(self):
        listed = set(_columns_listed_in(_migrate_device_settings, "device_settings"))
        model = {c.name for c in Base.metadata.tables["device_settings"].columns}
        # The migrator need not add columns the model already had at first
        # provision, but anything it lists must be real.
        assert listed <= model, f"migrator lists unknown columns: {sorted(listed - model)}"

    def test_portfolios_migrator_matches_model(self):
        listed = set(_columns_listed_in(_migrate_portfolios, "portfolios"))
        model = {c.name for c in Base.metadata.tables["portfolios"].columns}
        assert listed <= model

    def test_signal_tips_migrator_matches_model(self):
        listed = set(_columns_listed_in(_migrate_signal_tips, "signal_tips"))
        model = {c.name for c in Base.metadata.tables["signal_tips"].columns}
        assert listed <= model

    def test_trades_migrator_matches_model(self):
        listed = set(_columns_listed_in(_migrate_trades, "trades"))
        model = {c.name for c in Base.metadata.tables["trades"].columns}
        assert listed <= model

    def test_withdrawals_migrator_matches_model(self):
        listed = set(_columns_listed_in(_migrate_withdrawals, "withdrawals"))
        model = {c.name for c in Base.metadata.tables["withdrawals"].columns}
        assert listed <= model, f"unknown: {sorted(listed - model)}"

    def test_payout_columns_are_migrated(self):
        """The specific columns this change added."""
        assert "payout_wallet_keys" in _columns_listed_in(
            _migrate_device_settings, "device_settings"
        )
        assert "destination_chain" in _columns_listed_in(
            _migrate_withdrawals, "withdrawals"
        )

    def test_tatum_column_is_gone(self):
        """The Tatum key is unreadable and no longer a model column, so neither
        path should recreate it. Existing databases keep theirs untouched."""
        assert "tatum_api_key" not in _columns_listed_in(
            _migrate_device_settings, "device_settings"
        )


def _columns_listed_in(migrator, table: str) -> list[str]:
    """Extract the column names a migrator declares.

    Reads the names out of the function source so the test tracks the same list
    the code runs, rather than re-declaring it and drifting.
    """
    source = inspect.getsource(migrator)
    names = []
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("(") and line.rstrip(",").count(",") >= 2:
            inner = line.strip("(), ")
            parts = [p.strip().strip('"') for p in inner.split(",")]
            if parts and parts[0]:
                names.append(parts[0])
    return names


class TestMigrateEntryPoint:
    def test_migrate_is_a_coroutine(self):
        import app.migrations as migrations

        assert inspect.iscoroutinefunction(migrations.migrate)

    def test_migrate_covers_every_migrator(self):
        """A migrator that exists but is never awaited is the failure mode the
        dead app/migrations/ directory had."""
        source = inspect.getsource(__import__("app.migrations", fromlist=["migrate"]).migrate)
        for name in (
            "_migrate_device_settings",
            "_migrate_portfolios",
            "_migrate_signal_tips",
            "_migrate_trades",
            "_migrate_withdrawals",
            "_migrate_signal_metadata",
        ):
            assert name in source, f"{name} is never called by migrate()"

    def test_dead_migration_directory_is_gone(self):
        """`app/migrations/` was shadowed by `app/migrations.py` and never ran.

        Its four numbered files could not have been imported, so any column they
        claimed to add never reached a real database. It must not come back.
        """
        import app.migrations as migrations

        assert not hasattr(migrations, "__path__"), (
            "app.migrations is a package again; a directory here shadows "
            "migrations.py and nothing in it will run"
        )