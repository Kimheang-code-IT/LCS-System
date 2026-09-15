export const DIRECTIONS = ['Import', 'Export', 'Transit', 'Re-export'] as const
export const CURRENCIES = ['USD', 'KHR', 'VND'] as const
export const TIMEZONES = ['Asia/Phnom_Penh', 'Asia/Ho_Chi_Minh', 'Asia/Bangkok', 'UTC'] as const
export const CONTAINER_TYPES = ['20GP', '40GP', '40HC', '45GP', '45HC'] as const
export const CONTAINER_STATUSES = ['Expected', 'Planned', 'Loaded', 'In Transit', 'Delivered', 'Returned'] as const
export const TRUCK_TYPES = ['1.5T', '2T', '3.5T', '5T', '8T'] as const
export const TRANSPORT_MODES = ['Road', 'Sea', 'Air', 'Rail'] as const
export const TRANSPORT_BY = ['Truck', 'Sea', 'Air', 'Rail'] as const
export const ACTIVE_STATUS = ['Active', 'Inactive'] as const
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

export const JOB_STATUS = [
  'Job Created',
  'Documents Received',
  'Transport Registered',
  'Customs Processing',
  'Customs Cleared',
  'In Transit',
  'Arrived Factory',
  'Delivered',
  'Financial Completed',
  'Closed',
] as const

export const CUSTOMS_STATUS = ['Preparing', 'Submitted', 'Processing', 'On Hold', 'Cleared'] as const
export const QUOTATION_STATUS = ['Draft', 'Sent', 'Accepted', 'Converted', 'Rejected', 'Superseded', 'Expired', 'Cancelled'] as const
export const DEBIT_NOTE_STATUS = ['Draft', 'Posted', 'Reversed', 'Cancelled'] as const
export const SERVICE_CHARGE_STATUS = ['Draft', 'Issued'] as const
export const JOB_WORKFLOW_STATUS = ['DRAFT', 'OPEN', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CLOSED', 'CANCELLED'] as const
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

export const LOCATION_TYPES = ['Port', 'Border', 'Factory', 'Yard', 'Warehouse', 'City'] as const
export const PLACE_ROLES = [
  'Pickup',
  'Origin',
  'Port of Loading',
  'Transit / Border',
  'Port of Discharge',
  'Delivery',
  'Destination',
  'Other',
] as const
export const EQUIPMENT_CATEGORIES = ['Container', 'Truck'] as const
export const CHARGE_CATEGORIES = ['Customs', 'Trucking', 'Vietnam', 'Cambodia', 'Port', 'Other'] as const
export const COUNTRIES = ['Cambodia', 'Vietnam'] as const

export const PLACE_CATEGORIES = ['Administrative', 'Port', 'Border Checkpoint', 'SEZ', 'Factory', 'Yard', 'Warehouse', 'City'] as const
export const TRANSPORT_TYPES = ['Truck', 'Vessel', 'Air', 'Rail', 'Multimodal'] as const
export const PARTY_ROLES = ['Customer', 'Supplier', 'Carrier', 'Customs Broker', 'Transport Operator'] as const
export const ACCOUNT_TYPES = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense'] as const
export const PERIOD_STATUS = ['OPEN', 'CLOSED'] as const
export const COMPONENT_INSTANCE_MODES = ['SINGLE', 'REPEATABLE'] as const
export const COMPONENT_INSTANCE_MODE_OVERRIDES = ['INHERIT', 'SINGLE', 'REPEATABLE'] as const
