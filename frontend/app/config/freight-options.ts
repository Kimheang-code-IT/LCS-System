/**
 * The lifecycle of a configured exchange rate. Only an APPROVED row is ever
 * applied to a document; the values are stored verbatim, so the labels are
 * declared beside them rather than derived from the text.
 */
export const CURRENCY_RATE_STATUSES = [
  { label: 'Pending', value: 'PENDING' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Inactive', value: 'INACTIVE' },
] as const
export const CONTAINER_STATUSES = ['Expected', 'Planned', 'Loaded', 'In Transit', 'Delivered', 'Returned'] as const
export const TRUCK_TYPES = ['1.5T', '2T', '3.5T', '5T', '8T'] as const
export const TRANSPORT_MODES = ['Road', 'Sea', 'Air', 'Rail'] as const
export const TRANSPORT_BY = ['Truck', 'Sea', 'Air', 'Rail'] as const
export const ACTIVE_STATUS = ['Active', 'Inactive'] as const

/**
 * Route stop roles. These values are stored on `job.places[].placeRole` and are
 * matched verbatim against the service-order header place keys by
 * `jobFieldsFromPlaces`, so changing a string here breaks that sync.
 */
export const PLACE_ROLES = ['Pickup', 'Port of Loading', 'Transit / Border', 'Destination'] as const
export const PAYMENT_STATUS = ['Unpaid', 'Partial', 'Paid', 'Overdue'] as const
export const PAYMENT_METHODS = ['Bank Transfer', 'Cash', 'Cheque'] as const
export const SERVICE_TYPES = [
  'Trucking',
  'Customs',
  'Vietnam Service',
  'Cambodia Service',
  'Container Service',
  'Other',
] as const

export const CUSTOMS_STATUS = ['Preparing', 'Submitted', 'Processing', 'On Hold', 'Cleared'] as const
export const QUOTATION_STATUS = ['Draft', 'Sent', 'Accepted', 'Converted', 'Rejected', 'Superseded', 'Expired', 'Cancelled'] as const
export const DEBIT_NOTE_STATUS = ['Draft', 'Posted', 'Reversed', 'Cancelled'] as const
export const SERVICE_CHARGE_STATUS = ['Draft', 'Issued'] as const
export const SHIPMENT_STATUS = ['Scheduled', 'Registered', 'In Transit', 'Arrived', 'Completed'] as const
export const DELIVERY_STATUS = ['Scheduled', 'Arriving', 'Unloading', 'Delivered', 'POD Received'] as const
export const DOCUMENT_STATUS = ['Required', 'Missing', 'Uploaded', 'Approved'] as const

export const DOCUMENT_TYPES = [
  'SO',
  'Invoice',
  'Packing List',
  'B/L',
  'Patent',
  'Truck Bill',
  'Customs Declaration',
  'Customs Fee Receipt',
  'Seal Document',
  'Debit Note',
  'Payment Advice',
  'POD',
  'Supporting Document',
  'Other',
] as const

export const JOB_CHECKLIST_TYPES = [
  'SO',
  'Invoice',
  'Packing List',
  'B/L',
  'Patent',
  'Transport Document',
  'Customs Declaration',
  'Customs Fee Receipt',
  'POD',
] as const

export const DEBIT_CHARGE_TYPES = [
  'Customs Clearance Fee',
  'Weight Station Charge',
  'Customs Seal',
  'Second Document Fee',
  'Overtime',
  'Infrastructure Fee',
  'Trucking Fee',
  'Fuel Surcharge',
  'Moc Bai Gate In / Out',
  'Lift On / Off',
  'Extra Return Container',
  'Cai Mep Yard Transfer',
  'Overnight / Standby',
  'Empty Container Pickup Fee',
  'Local Charge',
  'Customs Declaration Modification Fee',
  'Fine',
  'Other',
] as const

export const QUOTATION_CONDITIONS = [
  'Inspection Fee',
  'Standby Fee',
  'Extra Customs Sheet',
  'Carrier Local Charges',
  'Port Charges',
  'Lift On / Lift Off',
  'Extra Trucking Fee',
  'Customs Charges',
  'Fuel Surcharge',
] as const

export const PARTY_ROLES = ['Customer', 'Supplier', 'Company'] as const
export const ACCOUNT_TYPES = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense'] as const
export const PERIOD_STATUS = ['OPEN', 'CLOSED'] as const
export const COMPONENT_INSTANCE_MODES = ['SINGLE', 'REPEATABLE'] as const
export const COMPONENT_INSTANCE_MODE_OVERRIDES = ['INHERIT', 'SINGLE', 'REPEATABLE'] as const

/**
 * Financial document types, mirroring `DOCUMENT_TYPE_LABELS` in
 * `backend/app/modules/finance/service.py`. The codes are stored verbatim on
 * `financial_documents.document_type` and matched against
 * `posting_rules.document_type`, so both sides must stay in step; the backend
 * rejects anything outside this set when a posting rule is configured.
 *
 * A credit note mirrors the journal of the document it corrects, which is why it
 * appears here alongside its counterpart rather than as a discount field.
 */
export const FINANCIAL_DOCUMENT_TYPES = [
  'CUSTOMER_INVOICE',
  'CREDIT_NOTE',
  'SUPPLIER_BILL',
  'SUPPLIER_CREDIT_NOTE',
  'CUSTOMER_RECEIPT',
  'SUPPLIER_PAYMENT',
  'OTHER_INCOME',
  'OTHER_EXPENSE',
  'TRANSFER',
  'ADJUSTMENT',
] as const

export const FINANCIAL_DOCUMENT_STATUSES = ['ACTIVE', 'INACTIVE'] as const

/**
 * Document types whose money actually moves through a bank/cash account, mirroring
 * `PAYMENT_TYPES` in `backend/app/modules/finance/service.py`. Payment method,
 * financial account and value date describe a settlement, so they are only shown
 * for these types.
 */
export const PAYMENT_DOCUMENT_TYPES = ['CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT'] as const

/**
 * Document types that can be allocated against, mirroring `ALLOCATABLE_TYPES` in
 * `backend/app/modules/finance/posting.py`. Only an invoice or a bill carries an
 * outstanding balance for a receipt or payment to settle.
 */
export const ALLOCATABLE_DOCUMENT_TYPES = ['CUSTOMER_INVOICE', 'SUPPLIER_BILL'] as const

/**
 * Document types that can appear on an allocation: the invoice or bill being
 * settled, and the receipt or payment settling it.
 */
export const ALLOCATION_DOCUMENT_TYPES = [
  ...ALLOCATABLE_DOCUMENT_TYPES,
  ...PAYMENT_DOCUMENT_TYPES,
] as const

/** Document types that carry a due date, i.e. the ones settled on credit terms. */
export const CREDIT_TERM_DOCUMENT_TYPES = [...ALLOCATABLE_DOCUMENT_TYPES] as const
