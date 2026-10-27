#!/bin/sh
# Restore one PostgreSQL custom-format dump into a NEW isolated database.
#
# Usage (on the production host, after the runtime bundle has been deployed):
#   ./restore-db.sh /home/ubuntu/lcs-backups/freight-YYYYmmdd-HHMMSS.dump lcs_restore_YYYYmmdd
#
# Safety rules:
#   * The target must not already exist and must never be the production DB.
#   * The dump is verified with pg_restore --list before any database is created.
#   * The production container and database are not stopped or modified.
#   * This helper never restores over the live database and never deletes data.
#
# The target is left in place for verification. Drop it manually after the drill.
set -eu

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <backup.dump> <new_isolated_database>" >&2
    exit 2
fi

DUMP_FILE=$1
TARGET_DB=$2
COMPOSE_FILE=${COMPOSE_FILE:-/opt/lcs/compose.yml}
POSTGRES_SERVICE=${POSTGRES_SERVICE:-postgres}

if [ ! -s "$DUMP_FILE" ]; then
    echo "Dump file is missing or empty: $DUMP_FILE" >&2
    exit 2
fi

case "$TARGET_DB" in
    ''|*[!A-Za-z0-9_]*)
        echo "Target database name may contain only letters, digits and underscores." >&2
        exit 2
        ;;
esac

COMPOSE="docker compose -f $COMPOSE_FILE"

# Read the container's own credentials without printing them.
PG_USER=$($COMPOSE exec -T "$POSTGRES_SERVICE" sh -c 'printf %s "$POSTGRES_USER"')
PG_DB=$($COMPOSE exec -T "$POSTGRES_SERVICE" sh -c 'printf %s "$POSTGRES_DB"')

if [ "$TARGET_DB" = "$PG_DB" ]; then
    echo "Refusing to restore over the production database '$PG_DB'." >&2
    exit 2
fi

# Validate the dump before creating anything.
if ! $COMPOSE exec -T "$POSTGRES_SERVICE" pg_restore --list < "$DUMP_FILE" >/dev/null; then
    echo "Dump failed pg_restore --list verification: $DUMP_FILE" >&2
    exit 2
fi

EXISTS=$($COMPOSE exec -T "$POSTGRES_SERVICE" \
    psql -U "$PG_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'")
if [ "$EXISTS" = "1" ]; then
    echo "Target database already exists; refusing to overwrite it." >&2
    exit 2
fi

echo "Creating isolated database '$TARGET_DB'..."
$COMPOSE exec -T "$POSTGRES_SERVICE" \
    psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"$TARGET_DB\""

echo "Restoring $DUMP_FILE into '$TARGET_DB'..."
$COMPOSE exec -T "$POSTGRES_SERVICE" \
    pg_restore -U "$PG_USER" -d "$TARGET_DB" --no-owner --no-privileges < "$DUMP_FILE"

echo "Restore complete: $TARGET_DB"
echo "Verify row counts and financial totals before dropping this database."
