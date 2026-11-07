---
description: Inspect agent tooling without broad code or test execution
---

Audit the requested configuration/context scope only. Inspect existing project instructions,
.agents/context, .agents/skills and .opencode skills/commands/reviewer before adding anything.

Inspect MCP entries as names/status/auth-field presence only, never dump effective config,
credentials, headers, env values or private keys. Use available live tool discovery to
separate connected tools from configured/disabled/unavailable tools. Client commands must
be supported by the installed version; check help only when permitted, never bypass blocks.

Find duplicate/stale instructions and source-path references. Do not run full application
suites to audit prose; use /docs-check. Measure actual bytes/available usage, not invented
savings. Change only explicitly requested project configuration. No global/model/provider
changes, installs, MCP deployment or archive/skill removal without appropriate authorization.

Report working/configured-not-tested/optional/unavailable separately and stop.
