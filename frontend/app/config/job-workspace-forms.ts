import { FILE_ATTACHMENT_COLUMNS, type FreightField, type FreightFieldType, type FreightTable } from './freight-modules'
import { PLACE_ROLES } from './freight-options'
import {
  actualContainerRowDefaults,
  computeContainerPaymentLine,
  computeJobFinanceLine,
  containerPaymentRowDefaults,
  containerRequirementRowDefaults,
  jobFinanceLineRowDefaults,
  routePlaceRowDefaults,
} from '~/utils/table/line-table-rules'

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
    { key: 'containerType', label: 'Container Type', labelKey: 'freight.ui.cols.containerType', type: 'select', required: true },
    { key: 'quantity', label: 'Required', labelKey: 'freight.ui.requiredCol', type: 'number', required: true },
    { key: 'actualQuantity', label: 'Actual', labelKey: 'freight.ui.actualCol', type: 'number', computed: true },
    { key: 'remaining', label: 'Remaining', labelKey: 'freight.ui.remainingCol', type: 'number', computed: true },
    { key: 'description', label: 'Description', labelKey: 'freight.fields.description', type: 'text' },
  ],
addLabel: 'Add requirement',
    addLabelKey: 'freight.ui.addRequirement',
  rowDefaults: containerRequirementRowDefaults,
}

export const JOB_ACTUAL_CONTAINER_TABLE: FreightTable = {
  key: 'actualContainers',
  title: 'Actual containers',
  titleKm: 'កុងតឺន័រពិត',
  columns: [
    { key: 'containerNo', label: 'Container No.', labelKey: 'freight.fields.containerNo', type: 'text', required: true },
    { key: 'containerType', label: 'Type', labelKey: 'freight.ui.cols.containerType', type: 'select', required: true },
    { key: 'sealNo', label: 'Seal', labelKey: 'freight.fields.sealNo', type: 'text' },
    { key: 'netWeightKg', label: 'Net Weight', labelKm: 'ទម្ងន់សុទ្ធ', labelKey: 'freight.ui.cols.netWeight', type: 'number' },
    { key: 'grossWeightKg', label: 'Gross Weight', labelKm: 'ទម្ងន់សរុប', labelKey: 'freight.ui.cols.grossWeight', type: 'number' },
    { key: 'note', label: 'Note', labelKm: 'កំណត់សម្គាល់', labelKey: 'freight.ui.cols.note', type: 'note' },
    { key: 'trust', label: '', type: 'delete' },
  ],
  addLabel: 'Add Container',
  addLabelKey: 'freight.ui.addContainer',
  rowDefaults: actualContainerRowDefaults,
}

/**
 * Container payment grid. Discount is its own column (not an inline field of
 * the line total), notes open the shared row-note dialog from an icon-only
 * cell, and the trailing utility columns expose delete plus the per-row
 * invoice print handled by `JobContainers.vue`.
 */
export const JOB_CONTAINER_PAYMENT_TABLE: FreightTable = {
  key: 'containerPayments',
  title: 'Container payments',
  titleKm: 'ការទូទាត់តាមកុងតឺន័រ',
  columns: [
    { key: 'containerNo', label: 'Container No.', labelKm: 'លេខកុងតឺន័រ', labelKey: 'freight.fields.containerNo', type: 'select' },
    { key: 'feeType', label: 'Service / Fee', labelKm: 'សេវា / ថ្លៃ', labelKey: 'freight.ui.serviceFee', type: 'select', required: true },
    { key: 'quantity', label: 'Qty', labelKm: 'ចំនួន', labelKey: 'freight.ui.qty', type: 'number', required: true },
    { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកត្តរ', labelKey: 'freight.ui.unitPriceCol', type: 'number', required: true },
    { key: 'discountAmount', label: 'Discount', labelKm: 'បញ្ចុះតម្លៃ', labelKey: 'freight.ui.discountCol', type: 'number' },
    { key: 'lineTotal', label: 'Line Total', labelKm: 'សរុបជួរ', labelKey: 'freight.ui.lineTotal', type: 'number', computed: true },
    { key: 'note', label: 'Note', labelKm: 'កំណត់សម្គាល់', labelKey: 'freight.ui.cols.note', type: 'note' },
    { key: '_delete', label: '', type: 'delete' },
    { key: '_invoice', label: '', type: 'action', action: 'invoice' },
  ],
  addLabel: 'Add payment',
  addLabelKey: 'freight.ui.addPayment',
  computeRow: computeContainerPaymentLine,
  rowDefaults: containerPaymentRowDefaults,
  pricing: true,
}

/**
 * Single finance grid for the service-order Finance tab. It merges customer
 * charges, supplier expenses and finance documents into one row list, told
 * apart by the hidden `_kind` field. Only `_kind === 'EXPENSE'` rows are
 * editable — `JobFinance` locks the rest through `rowDisabled` and is the only
 * place that writes the grid back (expenses to `service_orders.data.expenses`).
 */
export const JOB_FINANCE_LINES_TABLE: FreightTable = {
  key: 'financeLines',
  title: 'Finance Lines',
  titleKm: 'បន្ទាត់ហិរញ្ញវត្ថុ',
  columns: [
    { key: 'type', label: 'Type', labelKm: 'ប្រភេទ', labelKey: 'freight.ui.cols.type', type: 'text', computed: true },
    { key: 'reference', label: 'Reference', labelKm: 'លេខយោង', labelKey: 'freight.ui.cols.reference', type: 'text' },
    { key: 'date', label: 'Date', labelKm: 'កាលបរិច្ឆេទ', labelKey: 'freight.ui.cols.date', type: 'date' },
    { key: 'description', label: 'Description', labelKm: 'បរិយាយ', labelKey: 'freight.ui.cols.description', type: 'text', required: true },
    { key: 'party', label: 'Party', labelKm: 'ភាគី', labelKey: 'freight.ui.cols.party', type: 'text' },
    { key: 'quantity', label: 'Qty', labelKm: 'ចំនួន', labelKey: 'freight.ui.qty', type: 'number' },
    { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកត្តរ', labelKey: 'freight.ui.unitPriceCol', type: 'number' },
    { key: 'amount', label: 'Amount', labelKm: 'ចំនួន', labelKey: 'freight.ui.cols.amount', type: 'number', computed: true },
    { key: 'outstanding', label: 'Outstanding', labelKm: 'នៅសល់', labelKey: 'freight.ui.outstandingAmount', type: 'number', computed: true },
    { key: 'status', label: 'Status', labelKm: 'ស្ថានភាព', labelKey: 'freight.ui.cols.status', type: 'text' },
    { key: 'remark', label: 'Remark', labelKm: 'កំណត់សម្គាល់', labelKey: 'freight.ui.cols.remark', type: 'text' },
  ],
  addLabel: 'Add expense',
  addLabelKey: 'freight.ui.addExpense',
  computeRow: computeJobFinanceLine,
  rowDefaults: jobFinanceLineRowDefaults,
}

export const JOB_ROUTE_TABLE: FreightTable = {
  key: 'places',
  title: 'Route',
  columns: [
    { key: 'placeRole', label: 'Role', labelKey: 'freight.ui.routeRole', type: 'select', options: PLACE_ROLES, required: true },
    { key: 'place', label: 'Place', labelKey: 'freight.ui.cols.place', type: 'text', required: true },
    { key: 'planned', label: 'Planned', labelKm: 'ផែនកាល្បង', labelKey: 'freight.ui.plannedCol', type: 'date' },
    { key: 'actual', label: 'Actual', labelKm: 'ជាក់ស្តែង', labelKey: 'freight.ui.actualCol', type: 'date' },
    { key: 'notes', label: 'Note', labelKm: 'កំណត់សម្គាល់', labelKey: 'freight.ui.cols.note', type: 'note' },
    { key: '_delete', label: '', type: 'delete' },
  ],
  addLabel: 'Add Route',
  addLabelKey: 'freight.ui.addRoute',
  rowDefaults: routePlaceRowDefaults,
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
