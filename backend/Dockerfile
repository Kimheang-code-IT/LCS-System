FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PATH="/usr/local/bin:$PATH"

COPY --from=uv /uv /uvx /bin/

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

# PostgreSQL client tools: required by the full disaster-recovery workflow
# (pg_dump / pg_restore in app/modules/backup/dr.py and scripts/full_backup.py).
# Version 16 comes from PGDG and must match the deployment server: pg_dump 17
# writes `SET transaction_timeout` that a PostgreSQL 16 server rejects during
# restore. The Dockerfile base is Debian trixie.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer (cached): resolve from the committed lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code. The app runs from /app (uvicorn adds "." to sys.path and
# alembic.ini sets prepend_sys_path = .), so the project is intentionally NOT
# built/installed: that avoids fetching a build backend such as setuptools.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
# Maintenance CLIs, runnable in a one-off container (nothing here runs on start):
# full disaster-recovery backup, and the explicit master-data/configuration seed.
COPY scripts ./scripts

# No storage directory: uploaded objects are processed in memory and written
# directly to Cloudflare R2 / Google Drive (Settings → Storage & Backup).
RUN chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4).read()" || exit 1

# Migrations are an explicit deploy step (see .github/workflows/production.yml).
# The image starts the API only; production compose supplies this command
# explicitly, so an older rollback image cannot run its former startup
# migration. Local dev compose adds the migration command explicitly.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
