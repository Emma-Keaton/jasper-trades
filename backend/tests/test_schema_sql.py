"""The schema SQL must agree with the ORM it was generated from.

`scripts/schema.sql` is generated from `app/models.py`, but its BACKFILL column
list is maintained by hand. Those two halves drifting apart is the failure this
catches, and it is a failure that only shows up in production: `CREATE TABLE IF
NOT EXISTS` silently does nothing on a table that already exists, so a column
added to the models but missing from the backfill is absent on every database
that was provisioned before that change. Nothing fails at deploy time. It fails
later, as "column does not exist", on the request that needed it.

The generated file is also checked, so a hand-edit of the SQL is caught.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from app.models import Base  # noqa: E402
from generate_schema import BACKFILL, PAPER_CAPITAL, render_backfill  # noqa: E402


def _columns(table: str) -> set[str]:
    return {c.name for c in Base.metadata.tables[table].columns}


class TestBackfillMatchesTheModels:
    @pytest.mark.parametrize("table", sorted(BACKFILL))
    def test_backfill_targets_a_real_table(self, table):
        assert table in Base.metadata.tables, (
            f"BACKFILL lists '{table}', which is not in the ORM metadata. "
            "Either the table was renamed or the backfill entry is stale."
        )

    @pytest.mark.parametrize("table", sorted(BACKFILL))
    def test_every_backfill_column_exists_in_the_model(self, table):
        """A column that is not in the ORM is dead weight in the SQL, and a
        strong hint that a rename was applied to only one of the two."""
        model_columns = _columns(table)
        for column, _definition in BACKFILL[table]:
            assert column in model_columns, (
                f"BACKFILL adds {table}.{column}, but the model has no such "
                f"column. Models: {sorted(model_columns)}"
            )

    def test_columns_added_recently_are_backfilled(self):
        """The payout columns are the regression this suite exists for."""
        assert ("payout_wallet_keys", "TEXT") in BACKFILL["device_settings"]
        assert any(
            column == "destination_chain" for column, _ in BACKFILL["withdrawals"]
        ), (
            "withdrawals.destination_chain must be backfilled; without it an "
            "existing database cannot record which network a payout went on"
        )

    def test_every_table_needing_backfill_is_present_in_the_list(self):
        """Guard against a new table being added to the models with no
        backfill entry at all."""
        for table in ("device_settings", "portfolios", "signal_tips", "trades",
                      "withdrawals", "signals"):
            assert table in BACKFILL


class TestRenderedBackfill:
    def test_uses_if_not_exists_so_it_is_rerunnable(self):
        sql = render_backfill()
        assert "ADD COLUMN IF NOT EXISTS" in sql
        # A bare ADD COLUMN would fail the second run.
        assert sql.count("ADD COLUMN IF NOT EXISTS") == sum(
            len(c) for c in BACKFILL.values()
        )

    def test_covers_every_backfilled_column(self):
        sql = render_backfill()
        for table, columns in BACKFILL.items():
            for column, _definition in columns:
                assert f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}"' in sql


def _strip_comments(sql: str) -> str:
    """Drop `--` comments so structural assertions cannot match prose.

    Without this, a header line reading "CREATE TABLE builds the full schema"
    registers as an unguarded CREATE TABLE.
    """
    return "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )


class TestGeneratedFile:
    """Check the emitted artifact itself, so hand-edits are caught."""

    @pytest.fixture(scope="class")
    def schema_sql(self) -> str:
        path = SCRIPTS / "schema.sql"
        if not path.exists():
            pytest.skip("schema.sql not generated; run scripts/generate_schema.py")
        return path.read_text(encoding="utf-8")

    def test_file_exists_and_is_not_stale(self, schema_sql):
        # A regenerated file always carries this banner.
        assert "scripts/generate_schema.py" in schema_sql

    def test_creates_every_table_in_the_orm(self, schema_sql):
        """Covers the nine tables under app/models_ext as well as app/models."""
        sql = _strip_comments(schema_sql)
        missing = [
            table
            for table in Base.metadata.tables
            if f"CREATE TABLE IF NOT EXISTS {table}" not in sql
        ]
        assert not missing, f"tables missing from schema.sql: {sorted(missing)}"

    def test_is_idempotent_by_construction(self, schema_sql):
        """No unguarded CREATE or DROP of a table: the file must be safe to
        re-apply."""
        import re

        sql = _strip_comments(schema_sql)
        creates = re.findall(
            r"CREATE TABLE (?!IF NOT EXISTS)(\w+)", sql, re.IGNORECASE
        )
        assert not creates, f"unguarded CREATE TABLE for {creates}"
        # DROP is deliberately excluded from this file; resets live in reset.sh.
        drops = re.findall(r"DROP TABLE", sql, re.IGNORECASE)
        assert not drops, "schema.sql must not drop tables; use scripts/reset.sh"

    def test_includes_the_backfill(self, schema_sql):
        assert "ADD COLUMN IF NOT EXISTS" in _strip_comments(schema_sql)

    def test_seeds_the_paper_capital(self, schema_sql):
        assert "'__system__'" in schema_sql
        assert f"{PAPER_CAPITAL}" in schema_sql

    def test_seed_inserts_do_not_conflict(self, schema_sql):
        """A seed that can conflict would abort the file partway through."""
        assert schema_sql.count("ON CONFLICT DO NOTHING") == 2

    def test_seed_columns_exist(self, schema_sql):
        """The seed inserts name columns explicitly; a rename would make the
        insert fail at runtime."""
        portfolios = _columns("portfolios")
        for column in (
            "device_id",
            "name",
            "cash",
            "initial_value",
            "initial_capital",
            "is_paper",
            "is_active",
        ):
            assert column in portfolios

        settings = _columns("device_settings")
        for column in (
            "device_id",
            "trading_mode",
            "environment_mode",
            "universal_paper_trading_config",
        ):
            assert column in settings


class TestPaperCapitalIsConsistent:
    def test_paper_capital_matches_the_portfolio_defaults(self):
        """The old reset scripts hard-coded $10k in three places and drifted.
        The seed must agree with the model defaults."""
        for column in ("cash", "initial_value", "initial_capital"):
            col = Base.metadata.tables["portfolios"].columns[column]
            assert col.default is not None, f"portfolios.{column} has no default"
            assert float(col.default.arg) == PAPER_CAPITAL, (
                f"portfolios.{column} defaults to {col.default.arg}, but the "
                f"seed uses {PAPER_CAPITAL}"
            )

    def test_no_stale_reset_scripts_remain(self):
        """The two reset scripts were near-duplicates that diverged. Only one
        schema file and one reset entry point should exist."""
        scripts_dir = BACKEND / "scripts"
        stragglers = [
            p.name
            for p in scripts_dir.glob("*.sql")
            if p.name not in {"schema.sql"}
        ]
        assert not stragglers, (
            f"stale SQL files present: {stragglers}. schema.sql is authoritative; "
            "destructive resets belong in scripts/reset.sh."
        )