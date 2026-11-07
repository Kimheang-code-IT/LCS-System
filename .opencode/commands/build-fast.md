---
description: Build only artifacts affected by the current task
---

Identify task-owned changed paths and why they can break a build. Skip prose-only work.
Frontend build-affecting config/dependency/asset/bundling changes may need pnpm generate from
frontend/. An ordinary view change uses focused lint/types/behavior checks first.
Backend Python has no standalone compile artifact; do not import app.main merely to check
agent prose. Run affected code checks only when behavior/imports change.
Docker build is appropriate only for affected Dockerfile/dependency/infrastructure behavior
and authorized scope. No deployment, --no-cache, pruning, destructive reset or down -v.
Never rebuild just to run tests. Preserve caches; do not install dependencies unnecessarily.
Report built/skipped/failed with reason and exact command.
