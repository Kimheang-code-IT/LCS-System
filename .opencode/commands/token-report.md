---
description: Report measured token and tool usage for this project
---

Report what OpenCode has actually recorded. Do not estimate savings and never present an
estimated compression ratio as a provider saving.

1. Cost and tokens for this project: `opencode stats --project . --cost --limit 15`.
2. Tool reliability and call volume: `opencode stats --project . --tools --limit 15`.
3. Model mix: `opencode stats --project . --models --limit 10`.
4. Session window usage: ask the user for the context meter reading, or run
   `opencode api get /api/info` to confirm the service is healthy.
5. Fixed context cost, measured by file size rather than guessed:
   `Get-Item AGENTS.md, README.md | Select-Object Name,Length` and the total size of
   `.opencode/skills/*/SKILL.md`. Only the `AGENTS.md` and `README.md` cost is paid on
   every request; a skill is paid only when it loads.

Summarize: calls per tool, which tools fail, whether skill loads dominated the session,
and the one change with the clearest measured benefit. Label anything unmeasured as
unmeasured.
