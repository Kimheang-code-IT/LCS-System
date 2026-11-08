---
name: lcs-operations
description: Change LCS quotation, Service Order, actual-container, service-charge or operational-report workflows while preserving snapshots and source links.
---

# lcs-operations

Purpose/modules: quotations → operations → charges and operational reports, with master-data
and finance boundaries. Load only the affected [map row](../../context/module-map.md),
[business lifecycle](../../../docs/02-business/business-rules.md), relevant P05/P06/P07/P12
package and current Handoff. Use the existing backend/frontend implementation skills as needed.

Workflow: inspect current service, model, metadata, client adapter and tests first. Keep
multiple intentional SOs per quotation, independent saved pricing and individually identified
actual containers. Check idempotency source/payload ownership and existing conversion ledger.
Save/Finish is operational; charge issue/conversion is separate from financial posting.
Never copy current catalog prices over history or duplicate charge calculations.

Validation: quotation→SO transactions are DEEP; test success, invalid source/ownership,
replay and racing commands against a disposable PostgreSQL target when locking matters.
Other changes use [risk policy](../../../docs/03-development/testing-guide.md), existing tests
and a short manual journey. SQLite cannot prove PostgreSQL races. No live customer data.

Complete when the requested slice is verified, its affected task/Handoff updated and limits
reported. Do not start the next phase or rewrite historical rows.
