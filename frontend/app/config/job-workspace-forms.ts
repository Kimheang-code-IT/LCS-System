import { FILE_ATTACHMENT_COLUMNS, type FreightField, type FreightFieldType, type FreightTable } from './freight-modules'
import { CONTAINER_STATUSES, CONTAINER_TYPES, PLACE_ROLES } from './freight-options'

function field(
  key: string,
  type: FreightFieldType = 'text',
  extra: Partial<FreightField> = {},
): FreightField {
  return {
    key,
    label: extra.label || key,
    type,
    ...extra,
  }
}

export const JOB_CONTAINER_REQUIREMENT_TABLE: FreightTable = {
  key: 'containerRequirements',
  title: 'Container Requirements',
  titleKm: 'តម្រូវការកុងតឺន័រ',
  columns: [
    { key: 'containerType', label: 'Container Type', labelKey: 'freight.ui.cols.containerType', type: 'select', options: CONTAINER_TYPES, required: true },
    { key: 'quantity', label: 'Required', labelKey: 'freight.ui.requiredCol', type: 'number', required: true },
    { key: 'actualQuantity', label: 'Actual', labelKey: 'freight.ui.actualCol', type: 'number', computed: true },
    { key: 'remaining', label: 'Remaining', labelKey: 'freight.ui.remainingCol', type: 'number', computed: true },
    { key: 'description', label: 'Description', labelKey: 'freight.fields.description', type: 'text' },
  ],
  addLabel: 'Add requirement',
  addLabelKey: 'freight.ui.addRequirement',
}

export const JOB_ACTUAL_CONTAINER_TABLE: FreightTable = {
  key: 'actualContainers',
  title: 'Actual containers',
  titleKm: 'កុងតឺន័រពិត',
  columns: [
    { key: 'containerNo', label: 'Container No.', labelKey: 'freight.fields.containerNo', type: 'text', required: true },
    { key: 'containerType', label: 'Type', labelKey: 'freight.ui.cols.containerType', type: 'select', options: CONTAINER_TYPES, required: true },
    { key: 'containerRequirementId', label: 'Requirement', labelKey: 'freight.ui.cols.requirement', type: 'select' },
    { key: 'sealNo', label: 'Seal', labelKey: 'freight.fields.sealNo', type: 'text' },
    { key: 'status', label: 'Status', labelKey: 'freight.fields.status', type: 'select', options: CONTAINER_STATUSES },
    {
      key: 'weightKg',
      label: 'Weight (kg)',
      labelKey: 'freight.ui.cols.weightKg',
      type: 'number',
      computed: true,
      inlineFields: [
        { key: 'netWeightKg', label: 'Net', labelKm: 'សុទ្ធ' },
        { key: 'grossWeightKg', label: 'Gross', labelKm: 'សរុប' },
      ],
    },
  ],
  addLabel: 'Add Container',
  addLabelKey: 'freight.ui.addContainer',
}

export const JOB_CONTAINER_PAYMENT_TABLE: FreightTable = {
  key: 'containerPayments',
  title: 'Container payments',
  titleKm: 'ការទូទាត់តាមកុងតឺន័រ',
  columns: [
    { key: 'feeType', label: 'Service / Fee', labelKey: 'freight.ui.serviceFee', type: 'select', required: true },
    { key: 'containerNo', label: 'Container', labelKey: 'freight.fields.containerNo', type: 'select' },
    { key: 'description', label: 'Description', labelKey: 'freight.fields.description', type: 'text' },
    { key: 'quantity', label: 'Qty', labelKey: 'freight.ui.qty', type: 'number', required: true },
    { key: 'unitPrice', label: 'Unit Price', labelKey: 'freight.ui.unitPriceCol', type: 'number', required: true },
    {
      key: 'lineTotal',
      label: 'Line Total',
      labelKey: 'freight.ui.lineTotal',
      type: 'number',
      computed: true,
      inlineFields: [
        { key: 'discountAmount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
        { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
      ],
    },
  ],
  addLabel: 'Add payment',
  addLabelKey: 'freight.ui.addPayment',
}

export const JOB_ROUTE_TABLE: FreightTable = {
  key: 'places',
  title: 'Route',
  columns: [
    { key: 'placeRole', label: 'Role', labelKey: 'freight.ui.routeRole', type: 'select', options: PLACE_ROLES, required: true },
    { key: 'place', label: 'Place', labelKey: 'freight.ui.cols.place', type: 'text', required: true },
    { key: 'plannedActual', label: 'Planned / Actual', labelKey: 'freight.ui.cols.plannedActual', type: 'date' },
    { key: 'notes', label: 'Notes', labelKey: 'freight.ui.cols.notes', type: 'text' },
  ],
  addLabel: 'Add Route',
  addLabelKey: 'freight.ui.addRoute',
}

export const JOB_FILE_TABLE: FreightTable = {
  key: 'attachments',
  title: 'Files',
  addLabel: 'Upload File',
  addLabelKey: 'freight.ui.uploadFile',
  kind: 'files',
  columns: FILE_ATTACHMENT_COLUMNS,
}

export const FINANCE_REVERSE_FORM_FIELDS: FreightField[] = [
  field('reason', 'textarea', {
    required: true,
    label: 'Reason',
    labelKey: 'freight.fields.reason',
    helpKey: 'freight.fieldHelp.reason',
    colSpan: 2,
  }),
]
