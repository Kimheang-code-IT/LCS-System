#!/bin/sh
# Factory reset: return the deployed stack to first-run state.
#
# Removes ALL business data, uploads and cached state while keeping the runtime
# (.env, images, TLS certificates, docker-compose file) intact:
#   * PostgreSQL: verified pre-reset dump, then schema dropped and re-migrated
#   * Redis: all keys flushed
#   * MinIO: every object in the attachment bucket deleted
#   * backend /app/storage volume: emptied
#
# The app then reports requiresSetup=true, so the first-run /auth/setup flow
# creates a fresh administrator. Identities and history are NOT preserved -
# that is the point of a factory reset; use the in-app delete/archive flows for
# anything selective.
#
# Usage (on the host, from the runtime directory):
#   ./factory-reset.sh --yes
#
# Without --yes it only prints the plan and the containers it would touch.
# The pre-reset dump is written to $HOME/lcs-backups and verified with
# pg_restore --list; the reset aborts if that verification fails.
set -eu

DEPLOY_DIR=${DEPLOY_DIR:-/opt/lcs}
COMPOSE_FILE=${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.prod.yml}
BACKUP_DIR=${BACKUP_DIR:-$HOME/lcs-backups}
# Host header the backend accepts (ALLOWED_HOSTS in docker-compose.prod.yml).
PUBLIC_HOST=${PUBLIC_HOST:-lcslog.minidev.in}

CONFIRM="false"
for arg in "$@"; do
    case "$arg" in
        --yes) CONFIRM="true" ;;
        --help|-h)
            sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown argument: $arg (use --yes to confirm)" >&2; exit 2 ;;
    esac
done

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

if docker info >/dev/null 2>&1; then
    DOCKER="docker"
elif sudo -n docker info >/dev/null 2>&1; then
    DOCKER="sudo -E docker"
else
    echo "Docker is not usable by this user." >&2
    exit 1
fi

cd "$DEPLOY_DIR"
COMPOSE="$DOCKER compose -f $COMPOSE_FILE"

if [ "$CONFIRM" != "true" ]; then
    cat <<EOF
Factory reset plan (nothing was changed):

  runtime          $DEPLOY_DIR
  database         DROP SCHEMA public CASCADE, recreate, alembic upgrade head
  redis            FLUSHALL
  attachments      delete every object in bucket \$S3_BUCKET
  uploads          empty the backend /app/storage volume
  pre-reset dump   $BACKUP_DIR/freight-<timestamp>.dump (verified)

The stack is then restarted and must report requiresSetup=true.
Re-run with --yes to execute.
EOF
    exit 2
fi

# --- helpers ----------------------------------------------------------------
container_id() { $COMPOSE ps -q "$1" 2>/dev/null | head -n 1; }

wait_healthy() {
    id="$(container_id "$1")"
    [ -n "$id" ] || return 1
    attempt=0
    while [ "$attempt" -lt 40 ]; do
        state="$($DOCKER inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || echo unknown)"
        [ "$state" = "healthy" ] && return 0
        attempt=$((attempt + 1))
        sleep 3
    done
    return 1
}

# --- 1. data services up ----------------------------------------------------
echo "==> Ensuring data services are running"
$COMPOSE up -d postgres redis minio
if ! wait_healthy postgres; then
    echo "PostgreSQL is not healthy; aborting before any deletion." >&2
    exit 1
fi

# --- 2. verified backup -----------------------------------------------------
echo "==> Backing up PostgreSQL"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/freight-$(date +%Y%m%d-%H%M%S).dump"
if ! $COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP_FILE"; then
    echo "Backup failed; aborting with nothing deleted." >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi
if [ ! -s "$BACKUP_FILE" ]; then
    echo "Backup is empty; aborting with nothing deleted." >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi
if ! $COMPOSE exec -T postgres pg_restore --list < "$BACKUP_FILE" >/dev/null; then
    echo "Backup failed pg_restore --list verification; aborting with nothing deleted." >&2
    exit 1
fi
sha256sum "$BACKUP_FILE" > "$BACKUP_FILE.sha256"
echo "    verified backup: $BACKUP_FILE"

# --- 3. stop the application ------------------------------------------------
echo "==> Stopping backend and frontend"
$COMPOSE stop backend frontend >/dev/null

# --- 4. PostgreSQL: drop and re-migrate -------------------------------------
echo "==> Dropping the database schema"
$COMPOSE exec -T postgres sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO \"$POSTGRES_USER\";"'

echo "==> Applying migrations"
$COMPOSE run -T --rm --no-deps backend alembic upgrade head
EXPECTED_HEAD="$($COMPOSE run -T --rm --no-deps backend alembic heads 2>/dev/null | awk 'NF && $1 !~ /^INFO/ {print $1; exit}')"
CURRENT_HEAD="$($COMPOSE run -T --rm --no-deps backend alembic current 2>/dev/null | awk 'NF && $1 !~ /^INFO/ {print $1; exit}')"
if [ -z "$EXPECTED_HEAD" ] || [ "$CURRENT_HEAD" != "$EXPECTED_HEAD" ]; then
    echo "Migration verification failed: expected=${EXPECTED_HEAD:-unknown} current=${CURRENT_HEAD:-unknown}" >&2
    echo "The database is empty and the stack is stopped. Restore $BACKUP_FILE with restore-db.sh." >&2
    exit 1
fi
echo "    schema at $CURRENT_HEAD"

# --- 5. Redis ---------------------------------------------------------------
echo "==> Flushing Redis"
$COMPOSE exec -T redis redis-cli FLUSHALL >/dev/null

# --- 6. Attachments ---------------------------------------------------------
echo "==> Purging the attachment bucket"
$COMPOSE run -T --rm --no-deps --entrypoint sh minio-init -c '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
    mc rm -r --force "local/$S3_BUCKET" >/dev/null 2>&1 || true
    mc mb --ignore-existing "local/$S3_BUCKET" >/dev/null
'

echo "==> Emptying the uploads volume"
UPLOADS_VOLUME="$($COMPOSE ps -q backend >/dev/null 2>&1 || true)"
BACKEND_ID="$($COMPOSE ps -a -q backend 2>/dev/null | head -n 1 || true)"
if [ -n "$BACKEND_ID" ]; then
    UPLOADS_VOLUME="$($DOCKER inspect -f '{{range .Mounts}}{{if eq .Destination "/app/storage"}}{{.Name}}{{end}}{{end}}' "$BACKEND_ID" 2>/dev/null || true)"
fi
if [ -n "$UPLOADS_VOLUME" ]; then
    $DOCKER run --rm -v "$UPLOADS_VOLUME:/data" alpine:3.20 sh -c 'find /data -mindepth 1 -delete'
    echo "    emptied volume $UPLOADS_VOLUME"
else
    echo "    uploads volume not found (stack never started?); skipping"
fi

# --- 7. start and verify ----------------------------------------------------
echo "==> Starting the stack"
$COMPOSE up -d --remove-orphans
if ! wait_healthy backend; then
    echo "Backend did not become healthy after the reset." >&2
    echo "Inspect: $DOCKER logs --tail 100 \$(docker compose ps -q backend)" >&2
    exit 1
fi

echo "==> Verifying first-run state"
SETUP_STATE="$($COMPOSE exec -T backend python -c "
import json, urllib.request
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/setup/status', headers={'Host': '$PUBLIC_HOST'})
print(json.load(urllib.request.urlopen(req, timeout=5))['data']['requiresSetup'])
" 2>/dev/null | tr -d '\r' | tail -n 1)"

if [ "$SETUP_STATE" != "True" ]; then
    echo "Reset finished but the API does not report requiresSetup=true (got: ${SETUP_STATE:-no answer})." >&2
    exit 1
fi

cat <<EOF

Factory reset complete.
  pre-reset dump   $BACKUP_FILE
  schema head      $CURRENT_HEAD
  first-run state  requiresSetup=true (open /auth/setup)

Verify in the browser: the setup screen must ask for a new administrator.
The dump is NOT deleted automatically; keep it until the new install is accepted.
EOF
