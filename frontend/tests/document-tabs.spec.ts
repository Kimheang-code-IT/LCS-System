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
    expect(tabs[0]?.sections.map(section => section.id)).toEqual([
      'general',
      'classification',
      'location',
      'coordinates',
      'control',
    ])
    expect(tabs[0]?.sections.flatMap(section => section.fields.map(field => field.key))).toContain('code')
  })

  it('uses quotation schema tabs with line tables', () => {
    const module = getFreightModule('/quotations')
    const tabs = moduleDocumentTabs(module!)
    expect(tabs.map(tab => tab.id)).toEqual([
      'overview',
      'route',
      'containers',
      'pricing',
      'files',
      'revisions',
    ])
    expect(tabs[0]?.sections[0]?.fields.map(field => field.key)).toEqual([
      'customer',
      'branchName',
      'direction',
      'date',
      'validUntil',
      'currency',
      'description',
      'notes',
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
      'activity',
    ])
    expect(finance.find(tab => tab.id === 'traceability')?.sections[0]?.fields.map(field => field.key)).toEqual([
      'sourceChargeId',
      'journalId',
      'sourceRelationships',
    ])
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
        customer: 'Acme',
        branchName: 'Bavet',
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

  it('puts discount and tax under line total on quotation pricing lines', () => {
    const inlineFields = [
      { key: 'discountAmount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
      { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
    ]
    const field = moduleDocumentTabs(getFreightModule('/quotations')!)
      .find(tab => tab.id === 'pricing')?.sections[0]?.fields[0]
    expect(field?.meta?.showPricingTotals).toBe(true)
    const lineTotal = (field?.meta?.table as { columns: Array<{ key: string, inlineFields?: unknown[], labelKey?: string }> })
      .columns.find(column => column.key === 'lineTotal')
    expect(lineTotal?.labelKey).toBe('freight.ui.lineTotal')
    expect(lineTotal?.inlineFields).toEqual(inlineFields)
  })

  it('enables charge number input for standalone draft service charges', () => {
    const manual = moduleDocumentTabs(getFreightModule('/service-charges')!, {
      chargeManualNumber: true,
    }).find(tab => tab.id === 'general')?.sections[0]?.fields.find(field => field.key === 'chargeNo')
    const linked = moduleDocumentTabs(getFreightModule('/service-charges')!, {
      chargeLinkedToJob: true,
      chargeManualNumber: false,
    }).find(tab => tab.id === 'general')?.sections[0]?.fields.find(field => field.key === 'chargeNo')

    expect(manual?.readOnly).toBe(false)
    expect(manual?.helpKey).toBe('freight.fieldHelp.chargeNoManual')
    expect(linked?.readOnly).toBe(true)
    expect(linked?.helpKey).toBe('freight.fieldHelp.chargeNo')
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
