# Agent tooling and efficient context

Owner: agent setup, discovery and optional MCP policy. Verified by source/config inspection
2026-11-04; connection and runtime discovery status are separate below. No global config,
model, credential, provider, deployment or application behavior was changed.

## One task, one context path

AGENTS.md → .agents/context/project-context.md → selected roadmap/Handoff/task → module-map
row → owning requirement/source ranges. decisions.md stores dated pointers, not a second
specification. Use the existing phase package's goal/current evidence/tasks/dependencies/
acceptance/verification/status; do not create another roadmap or reread all P00–P16 packages.

Search filenames or exact symbols first, then callers/imports and focused surrounding lines.
For unknown ownership use one lean-ctx compose query; then targeted search/read. Recover
missing exact content from compression instead of repeating the command. If lean-ctx is
unavailable use scoped native search/read; never bypass a safety denial or disclose secrets.
No full-repository scan, repeated unchanged reads, logs in memory or invented percentage token
savings. Batch independent reads/test selectors; keep dependent edits/checks sequential.
Use one coding agent by default. Domain skills are on-demand instructions, not six agents.

## Skill discovery and reuse

[Official Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) describes
repository .agents/skills discovery and name/description metadata with the body loaded when
needed. [OpenCode v2 skills](https://opencode.ai/v2/docs/skills) documents project .opencode/skills
and .agents/skills compatibility; [v1 skills](https://opencode.ai/docs/skills/) also documents
.agents compatibility. These files use common name/description YAML, no invented config keys.

| Shared skill in .agents/skills/ | Use |
|---|---|
| lcs-architecture | Cross-module boundaries, contracts and reuse |
| lcs-operations | Quotation/SO/container/charge workflows and operational reports |
| lcs-finance | Posting, allocation, journals, periods, numbering and financial reports |
| lcs-ui | Shared UI, validation and A4/bilingual printing |
| lcs-quality | Risk-based validation and honest evidence |
| lcs-documentation | Canonical docs, context, decision pointers and handoffs |

Existing .opencode/skills/ retains lcs-development (thin router), fastapi-backend,
nuxt-frontend, database-migration and security-rbac implementation detail. Shared skills link
needed detail; do not copy those files into a second discovery directory. Codex can read a
linked file explicitly even if it does not automatically discover .opencode. New skills
are instruction-only, automatically eligible under host defaults, with no tool dependencies.
Use the host skill picker/$lcs-finance where supported, or request the file by path. OpenCode
uses its native skill mechanism. Fresh-session discovery still needs a local client check;
valid frontmatter alone does not prove loading by the installed client version.

The ten .opencode/commands are OpenCode command files, not Codex slash commands. Codex follows
the same documented workflow or reads a command file explicitly. DEEP uses a read-only review;
.opencode/agents/reviewer.md is OpenCode metadata, not a Codex subagent configuration. If a
host lacks safe independent review, disclose that missing gate rather than claiming it passed.

## Inspected integration status

| Capability | Observed configuration / availability | Status |
|---|---|---|
| lean-ctx MCP | Registered in inspected Codex/OpenCode user configs; ctx read/search/shell used successfully in this task | Installed and working in this Codex session; OpenCode connection not probed |
| Node REPL | Codex registration and successful local file/config operations | Installed and working in this session |
| Browser-automation MCP | Removed from `opencode.jsonc` 2026-11-06: browser acceptance is manual; restore only if the automated browser suite returns | Removed |
| Serena MCP | Inspected OpenCode user config: disabled:true | Configured but disabled; unavailable in this session |
| Ponytail | Project plugins names @dietrichgebert/ponytail@5.3.2 | Configured, plugin execution not tested |
| Context7 | No active entry in inspected project/user MCP configs and no exposed tool | Not available here; documented as optional |
| Graphiti | No entry in inspected configs and no exposed tool | Not available here; evaluated/deferred |
| New LCS skills | Six shared skills, common frontmatter and checked references | Files configured/validated; fresh-client discovery not tested |

This inventory is scoped to inspected files and the active tool catalog; it is not a claim
that no other profile/server installation exists. Only MCP names/status and credential-field
presence were inspected; secret values were not printed. Codex/OpenCode executables were
located, but the combined version command was rejected by lean-ctx's shell allowlist before
execution. No retry, allowlist change or bypass was used. Installed versions/effective merged
client configuration are unverified. Project config uses the documented OpenCode v2 shape.

## Context7 — optional version-specific library reference

[Official client setup](https://context7.com/docs/resources/all-clients) documents the hosted
https://mcp.context7.com/mcp endpoint and Codex/OpenCode client formats. Consult it for an
unfamiliar API, changed dependency behavior or compatibility question; local business logic
and simple copy do not need it. Match the lockfile version, resolve the library and query
only the needed feature. Reuse retrieved guidance while version/task assumptions hold.
Discover exposed tool names at runtime; do not assume a tool exists from this document.

No registration was added: there is no current library uncertainty requiring a live server.
If later enabled, inspect current effective config first and choose one plugin OR one MCP
registration. Prefer project scope; keep authentication in environment/OAuth, never a Git file.
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and
[OpenCode v2 MCP](https://opencode.ai/v2/docs/mcp-servers) own current client syntax. For example,
the following are documentation-only, NOT executed configuration:

~~~toml
# Optional project .codex/config.toml (trusted project); requires externally supplied token
[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"
bearer_token_env_var = "CONTEXT7_API_KEY"
~~~

~~~json
{
  "mcp": {
    "servers": {
      "context7": { "type": "remote", "url": "https://mcp.context7.com/mcp", "disabled": true }
    }
  }
}
~~~

The JSON is OpenCode v2 only; do not paste mcp.servers into v1 (which uses mcp.<name> and
enabled). Do not overwrite existing config or install a second integration. Confirm version,
merge safely, authenticate with the selected client's supported mechanism, then check its MCP
connection list and make one small library lookup before calling it working. Account quotas,
access and charges are not established by this setup. No paid service was enabled.

## Graphiti — evaluated, not deployed

The [upstream Graphiti MCP reference](https://raw.githubusercontent.com/getzep/graphiti/main/mcp_server/README.md)
uses a graph database (FalkorDB or Neo4j), inference and embeddings, with HTTP or stdio. Its
reference server lacks authentication/authorization and must not be exposed to untrusted
networks. A group_id namespace is not an access-control boundary.

Current recommendation: Git context/decisions plus targeted search already meet this
repository's needs; extra services are not justified by measured retrieval failures. No
Graphiti database, provider, server or credential was installed/configured/tested.

Before reconsidering: select supported inference/embedding providers, graph backend, owner,
isolation/auth proxy, backup/deletion policy and maintenance budget. Estimate recurring cost
as graph compute/storage + ingestion/query inference tokens + embedding tokens + backups;
no reliable dollar estimate exists until workload/providers are chosen. This task introduces
zero new paid-service charges. Local models replace API spend with hardware/quality costs.
Store only approved architecture/business facts with source, status and verification date;
exclude source dumps, customer transactions, credentials, full chats and debugging logs.
Reconcile retrieved facts against current approved docs; retire stale facts. Require explicit
approval for deployment/provider spending and verify one isolated non-sensitive lookup before
reporting a working integration.

## Workflow, risk and evidence

[Testing guide](testing-guide.md) owns FAST/STANDARD/DEEP and required integrity gates.
Documentation/simple copy: review and structural checks. Ordinary UI/CRUD: scoped lint/types,
manual journey and meaningful changed-logic regressions. Money/security/data integrity:
focused success/denial/boundary, transaction/rollback, idempotency/concurrency as applicable,
regression and independent review. Real PostgreSQL behavior needs a disposable target.
No automatic full-suite/build/browser/Compose run, dependency install or safety downgrade.

Update only affected task, decision/map and canonical doc. Report exact commands and limits;
stop after the requested task. For resume use the roadmap's unfinished S01/PLAN-0002 Handoff,
not completion of this environment task. Rich P10 closing stays future work.

## Setup verification record

Completed 2026-11-04 for the explicit agent-setup request only. No ERP feature implemented,
no next phase started, no dependency/server installed, no global config changed, no commit.

| Executed check | Observed result |
|---|---|
| Skill creator scripts/quick_validate.py using existing system Python | All 11 shared/existing skills validated across focused runs; fixed an existing unquoted colon in the Nuxt description. Bundled Python first lacked PyYAML; no package installed |
| Node REPL structural check, existing YAML/TypeScript parsers | 11 unique skills, 10 command frontmatters; project JSONC parses; 208 local links and 54 anchors resolve; 44 module entry paths and named tables checked |
| Source/API and selector inspection | All 44 mapped API entries located in router or master-data registration sources; 22 backend candidate test files exist. Operational report rows identify actual shared-store sources |
| git diff --check -- AGENTS.md .opencode/commands .opencode/skills (and affected docs scope) | Exit 0; added files also checked for trailing whitespace by structural validator |
| node scripts/feature-status.mjs --self-test | Passed, 12 mapped groups |
| node scripts/feature-status.mjs | Read-only routing completed; whole dirty-tree output includes unrelated earlier work, no ERP feature row promoted |
| SHA-256 baseline comparison | 828 selected non-secret existing source/docs/config files: 23 intended instruction/docs edits, no unexpected changes/deletions; 805 unchanged. 10 task-created files, all context/skills/tooling docs |

New files: .agents/context/{project-context,module-map,decisions}.md, six
.agents/skills/lcs-{architecture,operations,finance,ui,quality,documentation}/SKILL.md and this
agent-tooling document. Updated: AGENTS.md; five existing .opencode skills; all ten OpenCode
command files; docs/README.md; handbook, coding/testing/documentation standards; master roadmap
and phase tracker. The preexisting reviewer, deleted skills/plugins, application edits,
untracked migrations and previous printing artifacts were preserved. No task-created deletion.

The checks above are structural/source validation, not proof of skill selection quality or
live client/MCP integration. No application tests/build/browser/database run was needed or
claimed. Installed versions, fresh-session discovery and optional-server connections remain
unverified. Version/config commands blocked by tool policy were not retried or bypassed.
The temporary parser-import setup issue was corrected using the existing TypeScript package;
only sanitized configuration fields were reported.

Manual next-session check: open this repository in the desired client; confirm AGENTS/context
and the six skill names appear, then invoke one relevant skill for a small read-only module
question. Do not enable optional MCPs merely to test discovery. For a real continuation, read
S01/PLAN-0002 Handoff, finish its remaining action-gating/session acceptance before considering
S02; do not jump to rich P10 closing or infer acceptance from this setup.
