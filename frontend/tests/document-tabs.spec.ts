import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import {
  freightFieldToDocumentField,
  moduleDocumentTabs,
  RELATED_FIELD_KEY,
} from '../app/utils/freight/document-tabs'

describe('freightFieldToDocumentField', () => {
  it('maps freight types, options, computed, and help', () => {
    expect(freightFieldToDocumentField({
      key: 'name',
      label: 'Name',
      type: 'text',
      required: true,
    })).toMatchObject({
      key: 'name',
      labelKey: 'freight.fields.name',
      type: 'text',
      required: true,
    })

    expect(freightFieldToDocumentField({
      key: 'active',
      label: 'Active',
      type: 'checkbox',
    }).type).toBe('boolean')

    expect(freightFieldToDocumentField({
      key: 'secret',
      label: 'Secret',
      type: 'password',
    }).type).toBe('secret')

    expect(freightFieldToDocumentField({
      key: 'total',
      label: 'Total',
      type: 'number',
      computed: true,
    }).readOnly).toBe(true)

    expect(freightFieldToDocumentField({
      key: 'status',
      label: 'Status',
      type: 'select',
      options: ['Draft', { label: 'Open', value: 'OPEN' }],
    }).options).toEqual([
      { label: 'Draft', value: 'Draft' },
      { label: 'Open', value: 'OPEN' },
    ])

    expect(freightFieldToDocumentField({
      key: 'notes',
      label: 'Notes',
      type: 'textarea',
      helpKey: 'freight.fieldHelp.notes',
    })).toMatchObject({
      type: 'textarea',
      helpKey: 'freight.fieldHelp.notes',
      rows: 4,
    })

    expect(freightFieldToDocumentField({
      key: 'required',
      label: 'Required',
      type: 'checkbox',
      options: ['Yes', 'No'],
    })).toMatchObject({
      type: 'boolean',
      meta: { trueValue: 'Yes', falseValue: 'No' },
    })
  })
})

describe('moduleDocumentTabs', () => {
  it('compiles master data as one details tab with sections from field.section', () => {
    const module = getFreightModule('/master-data/places')
    expect(module).toBeTruthy()
    const tabs = moduleDocumentTabs(module!)
    expect(tabs.map(tab => tab.id)).toEqual(['details'])
    // Status is managed from the row "..." menu, so it is not a form field.
    expect(tabs[0]?.sections.map(section => section.id)).toEqual([
      'general',
      'location',
    ])
    const fieldKeys = tabs[0]?.sections.flatMap(section => section.fields.map(field => field.key)) ?? []
    expect(fieldKeys).toContain('code')
    expect(fieldKeys).not.toContain('status')
  })

  it('uses quotation schema tabs with line tables', () => {
    const module = getFreightModule('/quotations')
    const tabs = moduleDocumentTabs(module!)
    expect(tabs.map(tab => tab.id)).toEqual([
      'overview',
      'route',
      'pricing',
      'files',
      'revisions',
    ])
    expect(tabs[0]?.sections[0]?.fields.map(field => field.key)).toEqual([
      'customerPartyId',
      'customer',
      'direction',
      'date',
      'validUntil',
      'currency',
      'description',
    ])
    expect(tabs.find(tab => tab.id === 'pricing')?.sections[0]?.fields[0]).toMatchObject({
      type: 'line-table',
      key: 'pricingLines',
    })
  })

  it('compiles service charges and finance documents from tables', () => {
    const charges = moduleDocumentTabs(getFreightModule('/service-charges')!)
    expect(charges.map(tab => tab.id)).toEqual(['general', 'fee-lines', 'traceability'])
    expect(charges.find(tab => tab.id === 'traceability')?.sections[0]?.fields.map(field => field.key)).toEqual([
      'invoiceNo',
      'journalId',
      'sourceRelationships',
    ])

    const finance = moduleDocumentTabs(getFreightModule('/finance/documents')!)
    expect(finance.map(tab => tab.id)).toEqual([
      'overview',
      'lines',
      'allocation',
      'journal',
      'traceability',
      'files',
    ])
    expect(finance.find(tab => tab.id === 'traceability')?.sections[0]?.fields.map(field => field.key)).toEqual([
      'sourceChargeId',
      'journalId',
      'sourceRelationships',
    ])
  })

  it('scopes the financial-document fields and tabs to the document type', () => {
    const module = getFreightModule('/finance/documents')!
    const overview = (options: { documentType?: string, status?: string }) =>
      moduleDocumentTabs(module, options).find(tab => tab.id === 'overview')!
        .sections[0]!.fields.map(field => field.key)

    // An invoice settles on credit terms but never moves money through a bank
    // account: due date in, settlement fields out.
    const invoice = overview({ documentType: 'CUSTOMER_INVOICE' })
    expect(invoice).toContain('dueDate')
    expect(invoice).toContain('partyId')
    expect(invoice).toContain('total')
    expect(invoice).not.toContain('paymentMethod')
    expect(invoice).not.toContain('financialAccountId')
    expect(invoice).not.toContain('valueDate')

    // A receipt is the opposite: money moves, and there is nothing to settle later.
    const receipt = overview({ documentType: 'CUSTOMER_RECEIPT' })
    expect(receipt).toContain('paymentMethod')
    expect(receipt).toContain('financialAccountId')
    expect(receipt).toContain('valueDate')
    expect(receipt).not.toContain('dueDate')
  })

  it('hides the allocation and journal tabs where they cannot apply', () => {
    const module = getFreightModule('/finance/documents')!
    const tabIds = (options: { documentType?: string, status?: string }) =>
      moduleDocumentTabs(module, options).map(tab => tab.id)

    // Only an invoice, bill, receipt or payment carries allocations.
    expect(tabIds({ documentType: 'CUSTOMER_INVOICE' })).toContain('allocation')
    expect(tabIds({ documentType: 'CUSTOMER_RECEIPT' })).toContain('allocation')
    expect(tabIds({ documentType: 'TRANSFER' })).not.toContain('allocation')
    expect(tabIds({ documentType: 'ADJUSTMENT' })).not.toContain('allocation')

    // The journal exists once the document is posted, and a reversal posts a second.
    expect(tabIds({ documentType: 'CUSTOMER_INVOICE', status: 'Draft' })).not.toContain('journal')
    expect(tabIds({ documentType: 'CUSTOMER_INVOICE', status: 'Posted' })).toContain('journal')
    expect(tabIds({ documentType: 'CUSTOMER_INVOICE', status: 'Reversed' })).toContain('journal')

    // Lines, traceability and files apply to every type.
    const transfer = tabIds({ documentType: 'TRANSFER' })
    expect(transfer).toEqual(expect.arrayContaining(['overview', 'lines', 'traceability', 'files']))
  })

  it('keeps every tab and field when the document type is unknown', () => {
    const tabs = moduleDocumentTabs(getFreightModule('/finance/documents')!)
    expect(tabs.map(tab => tab.id)).toContain('journal')
    expect(tabs.map(tab => tab.id)).toContain('allocation')
    const fields = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields.map(field => field.key)))
    expect(fields).toContain('paymentMethod')
    expect(fields).toContain('dueDate')
  })

  it('puts roles on AppDocumentForm with a permission matrix field', () => {
    const tabs = moduleDocumentTabs(getFreightModule('/administration/roles')!)
    expect(tabs).toHaveLength(1)
    expect(tabs[0]?.sections.map(section => section.id)).toEqual(['main', 'permissions'])
    expect(tabs[0]?.sections[1]?.fields[0]?.type).toBe('permission-matrix')
  })

  it('puts named documentForm recipes on quotation, charge, finance, and roles modules', () => {
    expect(getFreightModule('/quotations')?.documentForm).toBe('quotation')
    expect(getFreightModule('/service-charges')?.documentForm).toBe('charges')
    expect(getFreightModule('/finance/documents')?.documentForm).toBe('finance')
    expect(getFreightModule('/administration/roles')?.documentForm).toBe('roles')
    expect(getFreightModule('/master-data/places')?.documentForm).toBeUndefined()
  })

  it('keeps required header fields on the compiled form so save can validate them', () => {
    const paths = ['/master-data/places', '/quotations', '/service-charges', '/finance/documents', '/administration/roles']
    for (const path of paths) {
      const module = getFreightModule(path)!
      const keys = new Set(
        moduleDocumentTabs(module).flatMap(tab =>
          tab.sections.flatMap(section => section.fields.map(field => field.key)),
        ),
      )
      const required = module.fields.filter(field => field.required && !field.computed)
      expect(required.length).toBeGreaterThan(0)
      for (const field of required) {
        expect(keys.has(field.key), `${path} missing ${field.key}`).toBe(true)
      }
    }
  })

  it('lets a filled master-data, quotation, and role record pass required-field save checks', () => {
    const fills: Record<string, Record<string, unknown>> = {
      '/master-data/places': { code: 'PPAP', name: 'Phnom Penh Autonomous Port' },
      '/quotations': {
        customerPartyId: '1',
        customer: 'Acme',
        direction: 'Import',
        date: '2026-08-27',
        currency: 'USD',
      },
      '/administration/roles': { code: 'OPS', name: 'Operations' },
    }
    for (const [path, extra] of Object.entries(fills)) {
      const module = getFreightModule(path)!
      const payload: Record<string, unknown> = { id: '' }
      for (const field of module.fields) payload[field.key] = field.type === 'date' ? '2026-08-27' : ''
      Object.assign(payload, extra)
      const missing = module.fields.filter(field =>
        field.required && !field.computed && !String(payload[field.key] ?? '').trim(),
      )
      expect(missing.map(field => field.key), path).toEqual([])
    }
  })

  it('builds quotation pricing lines with container, transport, qty, price and total', () => {
    const field = moduleDocumentTabs(getFreightModule('/quotations')!)
      .find(tab => tab.id === 'pricing')?.sections[0]?.fields[0]
    expect(field?.meta?.showPricingTotals).toBe(true)
    const columns = (field?.meta?.table as { columns: Array<{ key: string, type?: string, inlineFields?: unknown[] }> }).columns
    expect(columns.map(column => column.key)).toEqual([
      'containerType',
      'transportBy',
      'quantity',
      'unitPrice',
      'lineTotal',
      'trust',
    ])
    expect(columns.find(column => column.key === 'containerType')?.type).toBe('select')
    expect(columns.find(column => column.key === 'transportBy')?.type).toBe('select')
    // A quoted rate is the rate the customer pays: no discount or tax step, so the
    // line total carries no inline fields.
    expect(columns.find(column => column.key === 'lineTotal')?.inlineFields).toBeUndefined()
  })

  it('hides charge-managed fields on the service charge overview', () => {
    const module = getFreightModule('/service-charges')!
    const fields = moduleDocumentTabs(module, {
      chargeManualNumber: true,
    }).find(tab => tab.id === 'general')?.sections[0]?.fields ?? []
    const keys = fields.map(field => field.key)

    expect(keys).not.toContain('chargeNo')
    expect(keys).not.toContain('documentDate')
    expect(keys).not.toContain('documentType')
    expect(keys).not.toContain('status')
    // The service order link stays: the backend rejects a charge without it.
    expect(keys).toContain('jobNo')

    const columnKeys = module.columns.map(column => column.key)
    for (const hidden of ['chargeNo', 'documentDate', 'documentType', 'status']) {
      expect(columnKeys, hidden).not.toContain(hidden)
    }
  })

  it('puts discount and tax under grand total on charge fee lines with or without a job', () => {
    const inlineFields = [
      { key: 'discount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
      { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
    ]
    for (const chargeLinkedToJob of [true, false]) {
      const field = moduleDocumentTabs(getFreightModule('/service-charges')!, {
        chargeLinkedToJob,
        compact: true,
      }).find(tab => tab.id === 'fee-lines')?.sections[0]?.fields[0]
      expect(field?.meta?.includeTax).toBe(true)
      expect(field?.meta?.compact).toBe(true)
      const amount = (field?.meta?.table as { columns: Array<{ key: string, inlineFields?: unknown[], labelKey?: string }> })
        .columns.find(column => column.key === 'amount')
      expect(amount?.labelKey).toBe('freight.fields.total')
      expect(amount?.inlineFields).toEqual(inlineFields)
    }
  })

  it('appends related and can hide line tables on create', () => {
    const module = getFreightModule('/sales/companies')
    expect(module?.related?.length).toBeGreaterThan(0)
    const withRelated = moduleDocumentTabs(module!, { includeRelated: true })
    expect(withRelated.at(-1)).toMatchObject({
      id: 'related',
      sections: [{ fields: [{ key: RELATED_FIELD_KEY, type: 'related-records' }] }],
    })

    const quoted = getFreightModule('/quotations')!
    const createTabs = moduleDocumentTabs({ ...quoted, hideTablesOnCreate: true, tabs: moduleDocumentTabs(quoted) }, {
      isCreate: true,
    })
    expect(createTabs.some(tab => tab.sections.some(section => section.fields.some(field => field.type === 'line-table')))).toBe(false)
  })
})
