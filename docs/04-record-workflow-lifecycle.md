# Record Workflow Lifecycle

## Applicability

Required because quotations, financial records, periods and reference records have guarded
states. This document is in the agent reading order and maintenance policy.

## States and transitions

| Record | Main lifecycle | Guard / correction |
|---|---|---|
| Quotation revision | DRAFT → SUBMITTED → CONVERTED; re-quote creates a new draft revision | Legacy SENT/ACCEPTED rows keep their meaning and remain convertible; sent/submitted terms immutable; explicit authorized actions; duplicate conversion refused |
| Quotation exceptions | REJECTED, EXPIRED, SUPERSEDED, CANCELLED | Use only existing permitted transitions; ineligible revisions cannot convert |
| Service order | ACTIVE ⇄ INACTIVE | No invented completion/closure lifecycle; deactivate before deletion |
| Service charge | Draft → issued through existing action | Issue is informational; invoice conversion is a separate command |
| Financial document | DRAFT → POSTED → REVERSED; draft cancellation | Draft editable; posted history immutable; reversal/adjustment |
| Journal | DRAFT → POSTED → REVERSED; draft voiding | Balanced, open-period posting; immutable posted lines |
| Accounting period | OPEN → CLOSED; authorized reopen | Closed periods reject posting; reopening audited |
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

Quotation conversion must not duplicate a service order; conversion copies snapshots.
Source inspection of `backend/app/modules/quotations/service.py:1013–1053` distinguishes
same-`Idempotency-Key` replay (returns the original conversion payload) from another duplicate
(409 `DUPLICATE_CONVERSION`). The conflict is at quotation level; one quotation cannot create
another order by converting a different revision. S02 must exercise these cases; source
inspection alone is not passing runtime evidence.
Issued-charge conversion creates one idempotent financial draft and preserves source values.
Posting, allocation, reversal, and numbering use existing atomic/duplicate guards.
See [data invariants](02-data-model.md) and [API conventions](05-api-specification.md).

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
| FR-081 | A sent revision shall be immutable. |
| FR-082 | Users shall create a new revision when changing a sent revision. |
| FR-083 | The new revision shall copy the previous revision's commercial details unless the user changes them. |
| FR-084 | The system shall record accepted, rejected, expired, superseded, converted, and cancelled states. |
| FR-085 | Only an accepted revision shall be eligible for conversion. |
| FR-086 | Conversion shall require an explicit user action. |
| FR-087 | Conversion shall be idempotent and shall not create duplicate service orders for the same accepted revision. |
| FR-088 | The system shall create globally unique service-order numbers. |
| FR-089 | A service order shall preserve customer, trade direction, currency, description, and source-revision snapshots. |
| FR-090 | A service order shall use a simple `ACTIVE` / `INACTIVE` status. A saved order defaults to `ACTIVE`; the status is changed from the record's row action menu rather than the form. An active order cannot be deleted until it is deactivated, and the API rejects deleting an active order with conflict code `ORDER_ACTIVE`. |
| FR-091 | The system shall copy quotation container requirements to the service order. |
| FR-092 | The system shall keep container requirements separate from actual containers. |
| FR-093 | Users shall add actual containers with unique container numbers. |
| FR-094 | Users shall record container type, seal, status, net weight, and gross weight. |
| FR-095 | The system shall validate gross weight is not lower than net weight when both are present. |
| FR-096 | Users shall create, update, and complete service components according to their permissions. |
| FR-097 | Users shall attach files to service orders and components. |
| FR-098 | The system shall preserve operational history for completed components and recorded work; service orders retain ACTIVE / INACTIVE status rather than a closure state. |
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
