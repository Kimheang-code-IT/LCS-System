---
name: lcs-architecture
description: Trace LCS module boundaries, shared contracts and reuse before architecture changes or cross-module refactors.
---

# lcs-architecture

Purpose: keep the existing modular monolith coherent. Use for cross-module design; a known
one-line edit does not need architecture discovery.

Context: [module map](../../context/module-map.md), then only affected sections of
[architecture](../../../docs/01-architecture/system-architecture.md) and
[coding](../../../docs/03-development/coding-standards.md).

Workflow: locate the closest implementation; trace caller → API → service → model plus direct
consumers. Compare extending it with the smallest alternative. Check dependency direction,
cycles, contracts, permission grants and source snapshots. Plan material changes before edits.
Keep calculations/transactions server-side; do not create a competing repository/store/service.

Validation: use [risk policy](../../../docs/03-development/testing-guide.md); for shared
contracts include backend/tests/test_frontend_api_contract.py and test_route_authorization.py.
No browser or database work for a read-only architecture question.

Complete when the requested boundary/reuse question is answered or scoped change is verified;
record a stable decision only if new and approved. Report evidence/limits and stop.
