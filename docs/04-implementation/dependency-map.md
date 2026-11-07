# ERP dependencies

The S01–S13 [roadmap](master-plan.md) controls delivery. P numbers group topics;
they are not a simple numeric execution order. In particular, administration/access and
accounting setup must precede dependent operational/financial workflows.

## Package dependency graph as a table

| Package / task subset | Requires | Unlocks / reason |
|---|---|---|
| P00 | Safe working-tree snapshot | Documentation navigation and review boundaries |
| P01 | P00 | Actual code/test map for all later work |
| P02 | P01 | Existing shared UI/error/permission patterns, verified per caller |
| P03 | P01,P02 | Party/direction/type/fee/currency prerequisites and remaining master CRUD |
| P04 | P03 needed catalogs,P02 | Capturable configuration before S03 operational execution |
| P14.1 access/sequence subset | P01,P02; existing reference data as needed | S01 access; transaction-safe numbering for S02–S08 |
| P05 | S01,P03 needed catalogs,P04 required capture subset | Reusable quotation and safe conversion |
| P06 | P05,P04 operational subset | SO Save/Finish/physical operations and source snapshots |
| P09.1 accounts/rules/open period | S01,P03 finance catalogs,P14.1 | Posting setup required before P08; not all S08 correction work |
| P07 | P06,P09.1 draft conversion setup | Issued charges and once-only financial drafts |
| P08 | P07,P09.1,S01 | Invoice/receipt and bill/payment acceptance in S05,S06,S07 |
| P09.2–09.4 | P09.1; P08 posted fixture for corrections | S08 journals/reversal/custom-period integrity |
| P11.1 baseline reconciliation | P09.1; P08 posted/allocated fixture | Reliable GL/TB/AR/AP baseline needed by closing review |
| P10 | P09 controls,P11.1 baseline | Safe closing/reopening inside MOD-013 |
| P11 remaining reports | P08,P09 | S10 financial statements and output parity; no dependency on P10 |
| P12 | P06,P07,P08 comparison fixture | S09 operational reports without mixing estimated/posted |
| P13 | P11,P12 | Reconciled dashboard with per-metric access/date basis |
| P14 remaining admin | P01,P02,P03 | S11 settings/archive/audit acceptance |
| P15 | Relevant P03–P14 outcomes/S01–S11 | Final cross-module refusal/recovery scenarios |
| S12 recovery (existing slice) | Representative data + explicit isolated recovery authorization | P16 recoverability evidence; no new infrastructure implied |
| P16 | P15,S12,S01–S12 | S13 cross-browser/performance/accessibility/business release decision |

## One valid dependency-aware execution path

Resume remaining S01 first. Verify needed master/reference/sequence/accounting setup before
the slice that needs it. Then follow S02 → S03 → S04 → S05 → S06/S07 → S08 →
S09/S10 → remaining S11 → authorized S12 → S13. P10 can use P11.1 baseline verification
without requiring the full S10 report-delivery slice to start early.
S09 and S10 are ordered by roadmap while their prerequisite source checks may be performed
inside earlier owning slices. Task numbers inside a package are local; they do not authorize
executing unrelated later slices.

## Dependency safeguards

No circle: accounting setup does not require posted documents; report baseline reads synthetic
posted fixtures; closing uses that baseline; financial report implementation does not require
rich closing to exist. P14.1 prerequisite identity/numbering work is separate from remaining
admin acceptance. A failed prerequisite blocks only dependent tasks; no implicit scope expansion.


## Settings and integration task refinement

[PLAN-0005 task DAG](plans/PLAN-0005-settings-integrations.md#dependencies-and-recommended-order):
A audit → D1/D2 grant/secret/group-write foundation → B/C. B Developer delivery + D2 precede
E recovery; F needs D1 and necessary P03/P04 validators; G joins B–F outcomes. This refines
P03/P04/P06/P14/P15 and S12/P16, not a second roadmap. Runtime tasks remain NOT_STARTED and
need later implementation scope. S01 still resumes before dependent work.
