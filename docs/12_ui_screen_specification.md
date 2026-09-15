# UI Screen Specification

## 1. General UI Rules

- Use SvelteKit with permission-aware navigation.
- Display active organization and branch context in the header.
- Never rely on hidden buttons for authorization.
- Show validation errors beside the relevant field.
- Preserve unsaved draft state when safe.
- Use Khmer and English labels.
- Display currency and dates using organization/user settings.
- Show status badges consistently.
- Include an audit timeline on important aggregates.

## 2. Global Shell

### Header

Displays:

- organization selector;
- branch selector;
- current user;
- notifications;
- language selector;
- logout.

Branch selector behavior:

- list only assigned branches;
- show `All branches` only for organization-wide users;
- default to the user's default branch;
- reload branch-scoped lists after switching;
- preserve context in links and API requests.

### Navigation

Navigation groups:

- Dashboard.
- Quotations.
- Service Orders.
- Service Charges.
- Finance.
- Reports.
- Master Data.
- Configuration.
- Administration.

Menus are filtered by permission, but APIs enforce the final decision.

## 3. Dashboard

Widgets are scope-aware:

- open service orders;
- orders on hold;
- pending components;
- issued service charges;
- draft financial documents;
- overdue receivables;
- overdue payables;
- unallocated payments;
- current cash/bank balances;
- recent audit events.

Organization-wide users may compare branches. Branch users see only their assigned scope.

## 4. Administration Screens

### Organizations

Fields:

- organization code;
- legal name;
- display name;
- tax identifier;
- country;
- default currency;
- timezone;
- status.

### Branches

Fields:

- branch code;
- name;
- place;
- address;
- phone;
- email;
- head-office flag;
- status.

### Users

Screens:

- user list;
- invite user;
- user detail;
- session list;
- role assignments;
- branch assignments.

Assignment editor fields:

- role;
- organization;
- branch or all branches;
- effective date;
- expiry date.

### Roles and permissions

Show permissions grouped by resource. System roles require confirmation before changes. All changes display an audit warning.

### Accounting periods

Show period, dates, status, posting count, and close/reopen actions. Reopen requires a reason and elevated permission.

## 5. Master Data Screens

Each master-data screen includes:

- searchable list;
- filters;
- create action;
- edit action;
- activate/deactivate action;
- details drawer or page;
- audit history.

Required screens:

- parties and party roles;
- places;
- trade directions;
- container types;
- transport types;
- transport assets;
- fee types;
- financial accounts;
- chart of accounts.

## 6. Quotation Screens

### List

Filters:

- quotation number;
- customer;
- branch;
- direction;
- status;
- date range.

### Editor

Sections:

1. Header and customer.
2. Places and route.
3. Transport options.
4. Container requirements.
5. Pricing lines.
6. Attachments.
7. Revision history.

Actions depend on state:

- Save draft.
- Send.
- Create revision.
- Accept.
- Reject.
- Convert.
- Cancel.

Sent revisions show read-only fields and a `Create Revision` action.

## 7. Service-Order Screens

### List

Filters:

- order number;
- branch;
- customer;
- direction;
- status;
- date range.

### Detail layout

Header:

- order number;
- customer;
- branch;
- direction;
- status;
- source quotation.

Tabs:

- Overview.
- Places.
- Container requirements.
- Actual containers.
- Components.
- Service charges.
- Financial documents.
- Attachments.
- Audit timeline.

### Component editor

Render fields from template attributes:

- text;
- number;
- date;
- datetime;
- boolean;
- reference selector;
- structured JSON editor where explicitly configured.

Show:

- required indicator;
- validation message;
- template version;
- component status;
- completion metadata.

## 8. Service-Charge Screen

Fields:

- charge number;
- service order;
- branch;
- document type;
- document date;
- currency;
- fee lines;
- container link;
- quantity;
- unit amount;
- discount;
- tax;
- totals;
- remarks.

Actions:

- Save draft.
- Issue customer note.
- Download/print.
- Create finance invoice.

The screen must clearly display:

```text
Issuing this service charge does not post accounting.
```

## 9. Finance Screens

### Financial-document list

Filters:

- document number;
- document type;
- party;
- branch;
- service order;
- status;
- date range;
- currency.

### Financial-document editor

Fields:

- document type;
- party;
- branch;
- service order;
- document date;
- due date;
- currency;
- exchange rate;
- payment method;
- financial account;
- reference;
- lines;
- source relationships;
- attachments.

Actions:

- Save draft.
- Validate.
- Post.
- Allocate.
- Reverse.
- Print/download.

### Posting confirmation

Before posting, show:

- document total;
- accounting period;
- resolved debit account(s);
- resolved credit account(s);
- tax account;
- branch dimensions;
- balance difference.

Disable posting if balance difference is not zero or period is closed.

### Payment allocation

Show:

- payment total;
- already allocated amount;
- available amount;
- target outstanding amount;
- proposed allocation;
- currency/exchange rate.

## 10. Journal Screen

Display:

- entry number;
- source document;
- date;
- period;
- branch;
- status;
- journal lines;
- debit total;
- credit total;
- balance difference.

Posted journals are read-only. Reversal action requires reason and permission.

## 11. Attachment UX

1. User selects entity and attachment role.
2. UI requests a presigned upload URL.
3. UI uploads directly to object storage.
4. UI confirms completion.
5. API validates and marks the attachment available.
6. UI displays file name, version, size, uploader, and date.

## 12. Error and Empty States

Use clear messages for:

- no assigned branch;
- access denied;
- closed accounting period;
- missing required values;
- duplicate number;
- already converted;
- unbalanced journal;
- allocation exceeds balance;
- upload incomplete.

Do not reveal whether an inaccessible record exists in another organization.
