---
name: lcs-ui
description: Change LCS shared forms, tables, dialogs or A4 invoice/container printing using existing Nuxt components and bilingual layouts.
---

# lcs-ui

Purpose/modules: shared Nuxt UI, document views and print components. Read the affected
[map row](../../context/module-map.md), [UI rules](../../../docs/02-business/ui-ux-standards.md)
and relevant sections of [Nuxt implementation skill](../../../.opencode/skills/nuxt-frontend/SKILL.md).

Workflow: reuse metadata/views, repository contracts, shared validation/formatters and existing
print layouts before adding components. Preserve responsive/keyboard behavior, persistent
field/page errors, safe loading/refusal states and input after failure. Add locale keys to
en/km/zh only when copy changes. Never duplicate finance totals in a view.

For printing, inspect backend/app/modules/finance/printing.py and PLAN-0004. Use stored invoice
scope; Tax Invoice classification is not a generic title switch. Select an actual container
ID/number, never group by type; shared fees stay consolidated. Printing is read-only and keeps
the source number. Reuse supplied/configured assets, wait for fonts/images and verify A4,
Khmer/English, empty optional data, long rows, continuation headers, totals and signatures.

Validation: ordinary UI uses focused lint/typecheck and a short manual check; add meaningful
logic regressions as needed. Pure copy needs no financial suite. Browser/PDF tools only for
actual visual behavior. Billing-selection/security/money changes escalate to DEEP.

Complete when the requested behavior/layout is checked and exact verification/limits reported;
no new business page, finance module duplication or unrelated UI redesign.
