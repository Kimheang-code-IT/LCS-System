---
description: Reproduce a failure and apply the smallest scoped fix
---

Target: $ARGUMENTS

Capture the exact failure/test/HTTP response first without logging sensitive payloads.
Locate ownership once (lean-ctx compose when unknown), then exact symbols/callers and source
ranges. Trace client repository → API guard → service → model/query as relevant.
Run the failing selector and only checks suggested by the symptom. Avoid a generic battery
of backend/frontend/Docker/schema commands. Browser only for interaction/visual failures.
Fix the demonstrated cause without widened permissions, swallowed errors or unrelated refactor.
Add meaningful regression coverage and rerun the failed selector; broaden only for actual
impact/new evidence. DEEP integrity gates remain mandatory. Environment blockers are reported,
not papered over. Record affected files, exact evidence and manual check; stop at this issue.
