"""Driver-agnostic destructive database reset.

Drops every table in the target schema, then applies the single generated
`schema.sql`. Replaces two hand-maintained reset scripts
(`reset_db_p10k.sql`, `reset_db_supabase.sql`) that had drifted 626 lines apart,
contained no `ALTER TABLE ... ADD COLUMN`, and omitted the nine tables registered
under `app/models_ext`.

This exists because the deployment target is Supabase Postgres, where `psql` may
not be installed. It uses SQLAlchemy's asyncpg driver, which is already a project
dependency, so it works anywhere the backend runs.

    python scripts/reset_db.py "$DATABASE_URL"

Refuses to run unless the target actually looks like a jasper-trades database, so
a mistyped URL cannot wipe an unrelated schema.
"""

from __future__ import annotations

import asyncio
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

SCHEMA_FILE = os.path.join(BACKEND, "scripts", "schema.sql")

#: If the target does not have these, it is not a jasper-trades database.
SENTINEL_TABLES = ("portfolios", "device_settings", "trades")


def _async_url(url: str) -> str:
    """Normalise a Postgres URL to the asyncpg scheme SQLAlchemy needs."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


async def _reset(url: str) -> int:
    engine = create_async_engine(_async_url(url), future=True)
    try:
        async with engine.begin() as conn:
            present = set(
                (
                    await conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).scalars()
            )
            found = [t for t in SENTINEL_TABLES if t in present]
            if not found:
                print(
                    "Refusing to drop: the target has none of "
                    f"{', '.join(SENTINEL_TABLES)}.",
                    file=sys.stderr,
                )
                print(
                    "Check DATABASE_URL - this script drops every table in the "
                    "target schema.",
                    file=sys.stderr,
                )
                return 1

            print(f"Dropping {len(present)} tables ...")
            # One DROP per table rather than CASCADE-all: explicit, and it keeps
            # the output readable when something goes wrong.
            for table in sorted(present):
                await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    finally:
        await engine.dispose()

    with open(SCHEMA_FILE, encoding="utf-8") as handle:
        ddl = handle.read()

    engine = create_async_engine(_async_url(url), future=True)
    applied = 0
    try:
        async with engine.begin() as conn:
            for statement in _split_statements(ddl):
                await conn.execute(text(statement))
                applied += 1
    finally:
        await engine.dispose()

    print(f"Applied {applied} statements from schema.sql")
    return 0


def _split_statements(ddl: str) -> list[str]:
    """Split on semicolons at end of statement, ignoring comment-only lines.

    The generated SQL contains no dollar-quoted bodies or embedded semicolons in
    literals, so a statement-per-semicolon split is sufficient and keeps this
    free of a Postgres parser dependency.
    """
    statements: list[str] = []
    buffer: list[str] = []
    for line in ddl.splitlines():
        if line.lstrip().startswith("--"):
            continue
        buffer.append(line)
        if line.rstrip().endswith(";"):
            candidate = "\n".join(buffer).strip()
            if candidate.strip(";").strip():
                statements.append(candidate)
            buffer = []
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return asyncio.run(_reset(argv[1]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))