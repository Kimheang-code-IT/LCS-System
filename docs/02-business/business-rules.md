# Record Workflow Lifecycle

## Applicability

Required because quotations, financial records, periods and reference records have guarded
states. This document is in the agent reading order and maintenance policy.

## States and transitions

| Record | Main lifecycle | Guard / correction |
|---|---|---|
| Quotation revision | Save Changes → Submit; explicit quotation use creates an SO; Re-Quotation preserves revisions | No mandatory Send/Accept step; legacy states remain readable; multiple intentional SOs permitted, same-command retry deduplicated |
| Quotation exceptions | REJECTED, EXPIRED, SUPERSEDED, CANCELLED | Preserve historical meaning; target ineligible-source refusal requires S02 tests because current conversion has no state gate |
| Service order | Save persists operational work; ACTIVE → FINISHED through Finish; existing INACTIVE controls retained | Finish records actor/time and protects completed operations; inactive order cannot Finish; no automatic journal or full-settlement prerequisite |
| Service charge | Draft → issued through existing action | Issue is informational; invoice conversion is a separate command |
| Financial document | DRAFT → POSTED → REVERSED; draft cancellation | Draft editable; posted history immutable; reversal/adjustment |
| Journal | DRAFT → POSTED → REVERSED; draft voiding | Balanced, open-period posting; immutable posted lines |
| Accounting period | Existing DRAFT → OPEN → CLOSED; authorized reopen returns OPEN | Custom nonoverlapping dates; no user-entered year; closed periods reject posting; rich closing review remains target work |
| Reference/configuration | ACTIVE ⇄ INACTIVE where supported | Existing status policy; referenced records protected |
| Archive | Guarded soft delete → restore / guarded hard delete | Permissions and historical dependencies apply |

Service-charge wording above describes the business action, not an invented status enum.
Consult actual schemas/status-policy code before selecting API transition names.
Document types follow the reference rule with an archive step: canonical seeded types are
system records (deactivate only — deletion and archive are refused with
`SYSTEM_DOCUMENT_TYPE`); a custom type is deactivated first, may then be archived into the
central archive with an `ARCHIVE` audit event, and restores with its `ACTIVE`/`INACTIVE`
status and created-by evidence untouched. Archiving never changes lifecycle status, and an
archived type is not offered for new documents while existing documents keep their type.

## Transaction and retry behavior

Quotation use copies snapshots and permits multiple intentional service orders. The
2026-11-04 working-tree `quotations/service.py::convert_revision` no longer imposes a
one-order-per-quotation or revision-state gate. Same-`Idempotency-Key` replay returns the
original conversion; a concurrent losing request rolls back and reads the winner. New
intentional use gets a fresh key. Reusing a key for a different source/payload must be tested
and safely refused; optional-key source code alone does not prove retry acceptance.
`operations/service.py::save_service_order` selects the latest revision for new orders;
verify selected-revision fidelity, ineligible sources and every creation path in S02.
The normal Submit-first user journey is not proof that the backend currently enforces it.

Current Save/Finish bodies persist `FINISHED`, `finished_at` and `finished_by_user_id`.
Some UI metadata still uses ACTIVE_STATUS; action/list/edit guards need fresh verification.
Actual-container rows are entered manually, not precreated from quoted requirements.
The current master task supersedes former one-order and Active/Inactive-only requirements.
Issued-charge conversion creates one idempotent financial draft and preserves source values.
Posting, allocation, reversal, and numbering use existing atomic/duplicate guards.
See [data invariants](../01-architecture/database-design.md) and [API conventions](../01-architecture/api-design.md).

## Approvals and notifications

Existing permission-controlled business actions are sufficient for this release.
Do not introduce a second-person approval workflow. Telegram delivery is not a prerequisite
for committing a core transaction; reliability gaps remain separately tracked.

## Legacy requirement traceability

Stable identifiers migrated from the reviewed SRS. These are requirements, not assertions
that implementation or acceptance has passed. The approved LCS scope/priorities govern;
retired IDs and deferred advanced capabilities do not create extra pages or new workflows.

| ID | Requirement |
|---|---|
| FR-072 | Users shall create a quotation with customer and trade direction. |
| FR-073 | A quotation shall contain one or more revisions. |
| FR-074 | A revision shall contain currency, dates, descriptions, route stops, transport options, container requirements, and pricing lines. |
| FR-075 | A revision shall support multiple container types and quantities. |
| FR-076 | A pricing line shall optionally reference a container requirement. |
| FR-077 | A pricing line shall support fee type, description, quantity, unit, unit price, discount, tax, and calculated total. |
| FR-078 | The quotation revision shall use one currency for all lines. |
| FR-079 | The system shall calculate and display subtotal, discount, tax, and total amounts. |
| FR-080 | A draft revision shall be editable. |
| FR-081 | Submitted and legacy sent/accepted commercial revisions preserve immutable history. |
| FR-082 | Changed submitted commercial terms use a new draft revision. |
| FR-083 | The new revision shall copy the previous revision's commercial details unless the user changes them. |
| FR-084 | Preserve existing quotation/revision states and their historical meaning; do not add mandatory Sent/Accepted actions. |
| FR-085 | Explicit quotation use supports reusable offers and captured source revisions; normal Submit-first UI and backend source eligibility must be verified independently. |
| FR-086 | Conversion shall require an explicit user action. |
| FR-087 | Repeated execution of one keyed conversion returns one original SO; distinct intentional bookings may reuse the same quotation/revision. |
| FR-088 | The system shall create globally unique service-order numbers. |
| FR-089 | A service order shall preserve customer, trade direction, currency, description, and source-revision snapshots. |
| FR-090 | Save persists an operational SO; Finish records FINISHED with actor/time and locks prohibited operational edits without posting accounting. Preserve inactive and guarded deletion behavior; do not treat operational completion as settlement. |
| FR-091 | The system shall copy quotation container requirements to the service order. |
| FR-092 | The system shall keep container requirements separate from actual containers. |
| FR-093 | Users shall add actual containers with unique container numbers. |
| FR-094 | Users shall record container type, seal, status, net weight, and gross weight. |
| FR-095 | The system shall validate gross weight is not lower than net weight when both are present. |
| FR-096 | Users shall create, update, and complete service components according to their permissions. |
| FR-097 | Users shall attach files to service orders and components. |
| FR-098 | Preserve completed component and finished SO history, source snapshots and recorded work; corrections must not erase the original operational evidence. |
| FR-099 | Users shall create an informational service charge under a service order. |
| FR-100 | A service charge shall contain charge number, document type, date, currency, status, totals, and remarks. |
| FR-101 | A service charge shall contain multiple fee lines. |
| FR-102 | A fee line shall optionally reference a fee type. |
| FR-103 | A fee line shall optionally reference an actual service-order container. |
| FR-104 | A fee may apply to the whole service order when the container reference is null. |
| FR-105 | The system shall calculate service-charge totals from charge lines. |
| FR-106 | Issuing a service charge shall generate a customer-facing service note or configured document. |
| FR-107 | Issuing a service charge shall not create a journal entry. |
| FR-108 | An authorized user shall be able to create one idempotent draft customer invoice from an issued service charge; repeating the command shall return the same draft. |
| FR-109 | Conversion shall copy source values and shall not create a live mutable link. |
| FR-110 | Users shall be able to edit the generated financial draft before posting. |
| FR-110A | Charge conversion shall never post accounting; posting remains a separately authorized finance action. |
| FR-110B | Service-order profitability shall be calculated automatically from the accepted quotation, issued service charges, draft invoices, posted customer invoices, and posted supplier bills. |
