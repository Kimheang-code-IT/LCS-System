# Local CI scripts

Reproduce the GitHub Actions gates on a Windows machine **before** pushing, so
CI failures surface locally first. GitHub Actions remains authoritative; these
scripts mirror its required checks, they never contact production and never
touch production data.

## Commands

| Script | What it runs | Typical time |
|---|---|---|
| `scripts\ci-fast.ps1` | `uv lock --check`, backend `ruff check .`, backend test suite (`pytest -n auto`, sharded like Dev CI), frontend `pnpm lint`, `typecheck`, `vitest run`. Skips cleanly when `backend/.venv`/`frontend/node_modules` are missing | ~2-5 min |
| `scripts\ci-full.ps1` | Everything fast CI runs, plus: secret-pattern scan of tree **and git history**, `uv sync --frozen`, `bandit`, `pip-audit` (catches vulnerable-pinned dependencies like a `pyasn1 < 0.6.5` finding), `pnpm audit:security`, production `pnpm generate` build, compose config validation for `docker-compose.yml` and `docker-compose.prod.yml`, both Docker image builds, and an isolated container smoke test (backend image migrates a throwaway Postgres and passes `/health`; frontend image serves the SPA on `127.0.0.1:18080`) | ~15-30 min |

Both print a results table with per-check durations and exit non-zero when any
required check fails:

```
LOCAL CI RESULTS
Backend Lockfile (uv.lock)   PASS  (1.1s)
Backend Ruff                 PASS  (2.0s)
...
RESULT: READY TO PUSH
```

## Switches

- `-SkipBackendTests` (fast) — lint/typecheck/vitest only, when the backend is known green.
- `-Serial` — run pytest without CPU sharding (only to debug an xdist issue).
- `-SkipDocker` (full) — skip image builds + smoke (when Docker Desktop is off).

## Git pre-push hook (optional, explicit opt-in)

```powershell
.\scripts\install-hooks.ps1      # installs .git/hooks/pre-push; -Force overwrites
.\scripts\uninstall-hooks.ps1    # removes it again
```

Or bypass it for one push: `git push --no-verify`.

## Setup assumptions

- `uv`, `pnpm`, `node`, `git`, `docker` on PATH.
- `backend/.venv` reused when present; `uv sync --extra dev` created once if missing.
- pnpm store caching keeps installs incremental; Docker builds use the
  standard build cache (`backend/.dockerignore`, `frontend/.dockerignore`).

## Known differences from GitHub Actions runners

- Dev CI runs the three component gates **in parallel**; the local scripts run
  sequentially, so wall-clock times are the sum, not the max.
- Runners are Linux; several Windows-only differences are irrelevant because
  the tests are file/db/HTTP based, but path/encoding edge cases can differ.
- `pnpm audit:security` ignores CVEs that the repository policy explicitly
  waives (see `frontend/package.json` - same as CI).
- The container smoke test uses fixed throwaway names (`lcs-ci-*`) and
  `127.0.0.1:18080`; stop the dev stack or nothing else on the machine may
  use that port during a full run.