export type FreightReportColumn = {
  key: string
  label: string
  labelKey?: string
  numeric?: boolean
  status?: boolean
}

export type FreightReportFilter = 'branch' | 'party' | 'status' | 'currency' | 'date'

export type FreightReportDefinition = {
  slug: string
  group: 'operations' | 'finance'
  title: string
  titleKey: string
  description: string
  descriptionKey: string
  filters: FreightReportFilter[]
  columns: FreightReportColumn[]
  statement?: boolean
  statementTypes?: string[]
  statementFooterKey?: string
}

const col = (
  key: string,
  label: string,
  extra: Partial<FreightReportColumn> = {},
): FreightReportColumn => ({ key, label, ...extra })

const n = (key: string, label: string, extra: Partial<FreightReportColumn> = {}) =>
  col(key, label, { numeric: true, ...extra })

const status = (key: string, label: string, extra: Partial<FreightReportColumn> = {}) =>
  col(key, label, { status: true, ...extra })

function report(
  slug: string,
  group: FreightReportDefinition['group'],
  title: string,
  description: string,
  filters: FreightReportFilter[],
  columns: FreightReportColumn[],
  extra: Partial<FreightReportDefinition> = {},
): FreightReportDefinition {
  return {
    slug,
    group,
    title,
    titleKey: `freight.reportCatalog.reports.${slug}.title`,
    description,
    descriptionKey: `freight.reportCatalog.reports.${slug}.description`,
    filters,
    columns,
    ...extra,
  }
}

/** 12-report catalog. `ReportsView` and the sidebar read this list only. */
export const FREIGHT_REPORTS: FreightReportDefinition[] = [
  report('service-orders', 'operations', 'Service Order Register', 'Complete register of freight service orders.', ['branch', 'party', 'status', 'date'], [
    col('jobNo', 'Job No.', { labelKey: 'freight.fields.jobNo' }),
    col('date', 'Date', { labelKey: 'freight.ui.date' }),
    col('customer', 'Customer', { labelKey: 'freight.reportCatalog.columns.customer' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
    col('direction', 'Direction', { labelKey: 'freight.reportCatalog.columns.tradeDirection' }),
    n('containers', 'Containers', { labelKey: 'freight.jobSections.containers' }),
    n('components', 'Documents', { labelKey: 'freight.jobSections.documents' }),
    n('chargeTotal', 'Charge Total', { labelKey: 'freight.ui.totalCharges' }),
    n('invoiceTotal', 'Invoice Total'),
    status('workflowStatus', 'Status', { labelKey: 'freight.ui.status' }),
  ]),
  report('service-order-status', 'operations', 'Service Order Status', 'See job progress, aging, and pending operational work.', ['branch', 'party', 'status', 'date'], [
    col('jobNo', 'Job No.', { labelKey: 'freight.fields.jobNo' }),
    col('customer', 'Customer', { labelKey: 'freight.reportCatalog.columns.customer' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
    col('direction', 'Direction', { labelKey: 'freight.reportCatalog.columns.tradeDirection' }),
    col('createdAt', 'Created Date', { labelKey: 'freight.reportCatalog.columns.createdAt' }),
    status('workflowStatus', 'Status', { labelKey: 'freight.ui.status' }),
    n('daysOpen', 'Days Open'),
    n('pendingComponents', 'Pending Components'),
    col('lastActivity', 'Last Activity'),
  ]),
  report('containers', 'operations', 'Containers', 'Track actual containers attached to service orders.', ['branch', 'party', 'status'], [
    col('containerNo', 'Container No.', { labelKey: 'freight.ui.cols.containerNo' }),
    col('containerType', 'Container Type', { labelKey: 'freight.ui.cols.containerType' }),
    col('jobNo', 'Service Job', { labelKey: 'freight.reportCatalog.columns.serviceOrder' }),
    col('customer', 'Customer', { labelKey: 'freight.reportCatalog.columns.customer' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
    col('sealNo', 'Seal', { labelKey: 'freight.ui.cols.sealNo' }),
    status('status', 'Status', { labelKey: 'freight.ui.status' }),
    n('netWeightKg', 'Net Weight', { labelKey: 'freight.ui.cols.netWeight' }),
    n('grossWeightKg', 'Gross Weight', { labelKey: 'freight.ui.cols.grossWeight' }),
    col('currentMilestone', 'Current Milestone'),
  ]),
  report('profitability', 'operations', 'Profitability', 'Compare operational values with posted accounting results.', ['branch', 'party', 'currency', 'date'], [
    col('jobNo', 'Job No.', { labelKey: 'freight.fields.jobNo' }),
    col('customer', 'Customer', { labelKey: 'freight.reportCatalog.columns.customer' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
    n('quoted', 'Quoted'),
    n('serviceCharges', 'Service Charges'),
    n('postedRevenue', 'Posted Revenue', { labelKey: 'freight.reportCatalog.columns.revenue' }),
    n('postedCost', 'Posted Cost', { labelKey: 'freight.reportCatalog.columns.cost' }),
    n('grossProfit', 'Gross Profit', { labelKey: 'freight.reportCatalog.columns.profit' }),
    n('margin', 'Margin %', { labelKey: 'freight.reportCatalog.columns.margin' }),
  ]),
  report('revenue-expense', 'finance', 'Revenue & Expense', 'Posted revenue and expense activity for the selected period.', ['branch', 'party', 'currency', 'date'], [
    col('postingDate', 'Date', { labelKey: 'freight.reportCatalog.columns.postingDate' }),
    col('account', 'Account', { labelKey: 'freight.reportCatalog.columns.account' }),
    col('category', 'Category'),
    col('party', 'Party', { labelKey: 'freight.reportCatalog.columns.party' }),
    col('jobNo', 'Service Job', { labelKey: 'freight.reportCatalog.columns.serviceOrder' }),
    col('description', 'Description'),
    n('revenue', 'Revenue', { labelKey: 'freight.reportCatalog.columns.revenue' }),
    n('expense', 'Expense', { labelKey: 'freight.reportCatalog.columns.expense' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
  ]),
  report('accounts-receivable', 'finance', 'Accounts Receivable', 'Posted customer balances and aging.', ['branch', 'party', 'status', 'currency', 'date'], [
    col('invoiceNo', 'Invoice No.', { labelKey: 'freight.reportCatalog.columns.invoiceNo' }),
    col('customer', 'Customer', { labelKey: 'freight.reportCatalog.columns.customer' }),
    col('jobNo', 'Service Job', { labelKey: 'freight.reportCatalog.columns.serviceOrder' }),
    col('invoiceDate', 'Invoice Date'),
    col('dueDate', 'Due Date', { labelKey: 'freight.reportCatalog.columns.dueDate' }),
    n('total', 'Total', { labelKey: 'freight.reportCatalog.columns.total' }),
    n('paid', 'Paid'),
    n('outstanding', 'Outstanding', { labelKey: 'freight.reportCatalog.columns.outstanding' }),
    col('aging', 'Aging'),
    status('status', 'Status', { labelKey: 'freight.ui.status' }),
  ]),
  report('accounts-payable', 'finance', 'Accounts Payable', 'Posted supplier balances and aging.', ['branch', 'party', 'status', 'currency', 'date'], [
    col('invoiceNo', 'Bill No.', { labelKey: 'freight.reportCatalog.columns.billNo' }),
    col('supplier', 'Supplier', { labelKey: 'freight.reportCatalog.columns.supplier' }),
    col('jobNo', 'Service Job', { labelKey: 'freight.reportCatalog.columns.serviceOrder' }),
    col('billDate', 'Bill Date'),
    col('dueDate', 'Due Date', { labelKey: 'freight.reportCatalog.columns.dueDate' }),
    n('total', 'Total', { labelKey: 'freight.reportCatalog.columns.total' }),
    n('paid', 'Paid'),
    n('outstanding', 'Outstanding', { labelKey: 'freight.reportCatalog.columns.outstanding' }),
    col('aging', 'Aging'),
    status('status', 'Status', { labelKey: 'freight.ui.status' }),
  ]),
  report('general-ledger', 'finance', 'General Ledger', 'Posted accounting movement by ledger account.', ['branch', 'party', 'date'], [
    col('postingDate', 'Posting Date', { labelKey: 'freight.reportCatalog.columns.postingDate' }),
    col('journalNo', 'Journal No.'),
    col('sourceDocument', 'Source Document'),
    col('account', 'Account', { labelKey: 'freight.reportCatalog.columns.account' }),
    col('description', 'Description'),
    n('debit', 'Debit', { labelKey: 'freight.reportCatalog.columns.debit' }),
    n('credit', 'Credit', { labelKey: 'freight.reportCatalog.columns.credit' }),
    n('runningBalance', 'Running Balance', { labelKey: 'freight.reportCatalog.columns.balance' }),
    col('branchName', 'Branch', { labelKey: 'freight.reportCatalog.columns.branch' }),
  ]),
  report('trial-balance', 'finance', 'Trial Balance', 'Verify debit and credit balances from posted journals.', ['branch', 'date'], [
    col('accountCode', 'Account Code'),
    col('accountName', 'Account Name'),
    n('openingDebit', 'Opening Debit'),
    n('openingCredit', 'Opening Credit'),
    n('periodDebit', 'Period Debit'),
    n('periodCredit', 'Period Credit'),
    n('closingDebit', 'Closing Debit'),
    n('closingCredit', 'Closing Credit'),
  ]),
  report('profit-loss', 'finance', 'Profit & Loss', 'Operating result from posted revenue and expense accounts.', ['branch', 'currency', 'date'], [], {
    statement: true,
    statementTypes: ['Revenue', 'Expense'],
    statementFooterKey: 'freight.reportCatalog.netProfit',
  }),
  report('balance-sheet', 'finance', 'Balance Sheet', 'Financial position from posted asset, liability, and equity accounts.', ['branch', 'currency', 'date'], [], {
    statement: true,
    statementTypes: ['Asset', 'Liability', 'Equity'],
    statementFooterKey: 'freight.reportCatalog.difference',
  }),
  report('cash-flow', 'finance', 'Cash Flow / Cash & Bank', 'Posted cash and bank activity without unsupported classifications.', ['branch', 'currency', 'date'], [
    col('postingDate', 'Date', { labelKey: 'freight.reportCatalog.columns.postingDate' }),
    col('account', 'Account', { labelKey: 'freight.reportCatalog.columns.account' }),
    col('sourceDocument', 'Source'),
    col('journalNo', 'Reference'),
    col('party', 'Party', { labelKey: 'freight.reportCatalog.columns.party' }),
    col('description', 'Description'),
    n('cashIn', 'Cash In'),
    n('cashOut', 'Cash Out'),
    n('runningBalance', 'Running Balance', { labelKey: 'freight.reportCatalog.columns.balance' }),
  ]),
]

export function getFreightReport(slug: string) {
  return FREIGHT_REPORTS.find(item => item.slug === slug) || FREIGHT_REPORTS[0]!
}

export function freightReportPath(report: FreightReportDefinition) {
  return `/reports/${report.group}/${report.slug}`
}
