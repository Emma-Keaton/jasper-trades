#!/usr/bin/env bash
# DESTRUCTIVE: drop every jasper-trades table, then rebuild from schema.sql.
#
# This is the only sanctioned way to rebuild from empty. schema.sql on its own is
# non-destructive and idempotent: it creates what is missing and backfills
# columns added since, which is what you want against a live database.
#
# Usage:
#   psql "$DATABASE_URL" -f scripts/reset.sh          # needs psql; see below
#   python scripts/reset_db.py "$DATABASE_URL"        # driver-agnostic
#
# The two hand-maintained reset scripts this replaces (reset_db_p10k.sql,
# reset_db_supabase.sql) had drifted 626 lines apart, contained no
# ALTER TABLE ... ADD COLUMN, and omitted the nine tables under app/models_ext.
# Both problems are impossible now: this drops whatever is in the database and
# then applies the single generated file.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set." >&2
  echo "Refusing to drop tables without an explicit target." >&2
  exit 1
fi

# Guard against pointing this at something that is not a jasper-trades database.
if ! psql "$DATABASE_URL" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_name IN ('portfolios','device_settings','trades');" \
    | grep -qE '^[1-9]'; then
  echo "Refusing to drop: the target has no jasper-trades tables." >&2
  echo "Check DATABASE_URL - this script drops every table it is pointed at." >&2
  exit 1
fi

echo "Dropping all tables in $DATABASE_URL ..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')
  LOOP
    EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', r.tablename);
  END LOOP;
END $$;
SQL

echo "Rebuilding from schema.sql ..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$DIR/schema.sql"

echo "Done."