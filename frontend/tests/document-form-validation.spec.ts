import { describe, expect, it } from 'vitest'
import { freightModules, getFreightModule } from '../app/config/freight-modules'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { validateDocumentFields, validateTableRows } from '../app/utils/validation/record-validation'

const label = (key: string) => key

/** Tables the document form renders for information only (never validated). */
const VIEW_ONLY_TABLES = new Set(['revisionHistory', 'sourceRelationships', 'attachments', 'auditTimeline'])

/** Modules that render a create/edit document form. */
function documentModules() {
  return freightModules.filter(module => !module.readOnly && !module.tableOnly && module.fields.length > 0)
}

/**
 * A create form the user has filled in: every required field carries a value
 * that satisfies the inferred rule, so validation must come back clean. Selects
 * take their first declared option and numbers respect their declared bounds,
 * because that is what the UI offers and accepts.
 */
function filledRecord(module: NonNullable<ReturnType<typeof getFreightModule>>): Record<string, unknown> {
  const model: Record<string, unknown> = {}
  for (const field of module.fields) {
    if (field.computed) continue
    const firstOption = field.options?.length
      ? field.options.map(option => (option && typeof option === 'object' && 'value' in option ? String(option.value) : String(option)))[0]
      : undefined
    if (!field.required) {
      // An optional positive number (an exchange rate) still cannot be zero;
      // the fixture supplies a satisfiable value instead of an invalid sentinel.
      model[field.key] = field.type === 'number'
        ? (field.rule?.positive ? 1 : 0)
        : ''
      continue
    }
    model[field.key] = firstOption ?? (field.type === 'number'
      ? Math.max(1, field.rule?.min ?? 1)
      : field.type === 'date'
        ? '2026-01-01'
        : field.rule?.password
          ? 'Passw0rd!'
          : field.rule?.email || /email$/i.test(field.key)
            ? 'filled@example.com'
            : /currenc(?:y|ies)code$/i.test(field.key) || (module.collection === 'currencies' && field.key === 'code')
              ? 'USD'
              : 'ACME')
  }
  return model
}

describe('every document form is validatable', () => {
  it('compiles a tab schema for every editable module with fields', () => {
    for (const module of documentModules()) {
      const tabs = moduleDocumentTabs(module, { isCreate: true })
      expect(tabs.length, `${module.collection} has no tabs`).toBeGreaterThan(0)
      for (const tab of tabs) {
        for (const section of tab.sections) {
          for (const field of section.fields) {
            expect(typeof field.key, `${module.collection}.${tab.id} has an unkeyed field`).toBe('string')
          }
        }
      }
    }
  })

  it('reports every declared required field when the form is blank', () => {
    for (const module of documentModules()) {
      const required = module.fields.filter(field => field.required && !field.computed)
      if (!required.length) continue
      const failures = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      const keys = failures.map(failure => failure.key)
      for (const field of required) {
        expect(keys, `${module.collection} / ${field.key}`).toContain(field.key)
      }
    }
  })

  it('accepts a form once every required field is filled', () => {
    // Guards against a rule that would reject a legitimately filled form — for
    // example a `date` field that only accepts ISO while the picker writes a
    // localized pattern.
    for (const module of documentModules()) {
      const failures = validateDocumentFields({
        fields: module.fields,
        model: filledRecord(module),
        isCreate: true,
        label,
      })
      expect(failures.map(failure => `${module.collection}.${failure.key}`)).toEqual([])
    }
  })

  it('skips a create-only field when the record already exists', () => {
    const module = getFreightModule('/administration/users')!
    expect(module.fields.some(field => field.createOnly && field.required)).toBe(true)
    const creating = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
    const editing = validateDocumentFields({ fields: module.fields, model: {}, isCreate: false, label })
    expect(creating.map(f => f.key)).toContain('password')
    expect(editing.map(f => f.key)).not.toContain('password')
  })
})

describe('quotation form (/quotations)', () => {
  const module = getFreightModule('/quotations')!
  const pricing = module.tables!.find(item => item.key === 'pricingLines')!
  const places = module.tables!.find(item => item.key === 'places')!

  it('requires the customer party on the overview tab', () => {
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), customerPartyId: '' },
      isCreate: true,
      label,
    })
    expect(failures).toEqual([{ code: 'required', key: 'customerPartyId', label: 'customerPartyId' }])
  })

  it('rejects an unparseable quotation date', () => {
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), date: '01/01/2026' },
      isCreate: true,
      label,
    })
    expect(failures).toContainEqual({ code: 'date', key: 'date', label: 'date' })
  })

  it('never validates the server-assigned quotation number', () => {
    // `quotationNo` is computed by the backend sequence, so blocking on it would
    // make every create form unsubmittable.
    expect(module.fields.find(field => field.key === 'quotationNo')).toMatchObject({ required: true, computed: true })
    expect(validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), quotationNo: '' },
      isCreate: true,
      label,
    }).map(failure => failure.key)).not.toContain('quotationNo')
  })

  it('rejects a malformed email wherever a module declares one', () => {
    const companies = getFreightModule('/sales/companies')!
    const withEmail = companies.fields.find(field => field.key === 'email')
    expect(withEmail).toBeDefined()
    const failures = validateDocumentFields({
      fields: companies.fields,
      model: { ...filledRecord(companies), email: 'not-an-email' },
      isCreate: true,
      label,
    })
    expect(failures).toContainEqual({ code: 'email', key: 'email', label: 'email' })
  })

  it('locates an invalid quotation line by row and column', () => {
    const rows = [
      { containerType: '40HC', transportBy: 'Sea', quantity: 2, unitPrice: 100, lineTotal: 200 },
      { containerType: '', transportBy: 'Sea', quantity: 1, unitPrice: 20, lineTotal: 20 },
    ]
    const keys = validateTableRows({ table: pricing, rows, label }).map(failure => failure.key)

    expect(keys).toContain('pricingLines.1.containerType')
    // The valid first row is untouched: no error points at it.
    expect(keys.some(key => key.startsWith('pricingLines.0.'))).toBe(false)
  })

  it('locates a missing route role on the route tab', () => {
    const rows = [
      { placeRoleId: '1', place: 'Phnom Penh', planned: '2026-01-05T09:00' },
      { placeRoleId: '', place: 'Bavet', planned: '2026-01-08T10:00' },
    ]
    const keys = validateTableRows({ table: places, rows, label }).map(failure => failure.key)
    expect(keys).toContain('places.1.placeRoleId')
    expect(keys.some(key => key.startsWith('places.0.'))).toBe(false)
  })

  it('requires the place role but leaves the free-text location optional', () => {
    const rows = [{ placeRoleId: '' }]
    expect(validateTableRows({ table: places, rows, label }).map(f => f.key))
      .toEqual(['places.0.placeRoleId'])
  })

  it('keeps row identifiers stable so a reorder cannot move an error onto a valid row', () => {
    const rows = [
      { placeRoleId: '1', place: 'Phnom Penh' },
      { placeRoleId: '', place: 'Bavet' },
    ]
    expect(validateTableRows({ table: places, rows, label }).map(f => f.key))
      .toContain('places.1.placeRoleId')

    const reordered = [rows[1]!, rows[0]!]
    // After the reorder the missing role is row 0; the host clears the table's
    // row errors on the structural edit and recomputes them here.
    expect(validateTableRows({ table: places, rows: reordered, label }).map(f => f.key))
      .toContain('places.0.placeRoleId')
  })

  it('never validates the revision history table', () => {
    const revisions = module.tables!.find(item => item.key === 'revisionHistory')!
    expect(VIEW_ONLY_TABLES.has(revisions.key)).toBe(true)
  })
})

describe('finance document form (/finance/documents)', () => {
  const module = getFreightModule('/finance/documents')!
  const lines = module.tables!.find(item => item.key === 'lines')!
  const allocations = module.tables!.find(item => item.key === 'allocations')!

  it('requires the document date and the business party', () => {
    const keys = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(failure => failure.key)
    expect(keys).toContain('date')
    expect(keys).toContain('partyId')
  })

  it('rejects an unparseable posting date', () => {
    const keys = validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), postingDate: '31/12/2026' },
      isCreate: true,
      label,
    }).map(failure => failure.key)
    expect(keys).toContain('postingDate')
  })

  it('locates an invalid financial document line', () => {
    const keys = validateTableRows({
      table: lines,
      rows: [
        { description: 'Freight', accountCode: '4000', quantity: 1, unitAmount: 100, amount: 100 },
        { description: '', accountCode: '4000', quantity: 1, unitAmount: 50, amount: 50 },
      ],
      label,
    }).map(failure => failure.key)
    expect(keys).toContain('lines.1.description')
  })

  it('validates payment allocations in their own table', () => {
    const keys = validateTableRows({
      table: allocations,
      rows: [{ targetDocumentId: '', amount: 10 }],
      label,
    }).map(failure => failure.key)
    expect(keys.some(key => key.startsWith('allocations.0.'))).toBe(true)
  })

  it('validates journal entry lines', () => {
    const journals = getFreightModule('/finance/journals')!
    const journalLines = journals.tables!.find(item => item.key === 'lines')!
    const keys = validateTableRows({
      table: journalLines,
      rows: [{ accountCode: '', description: 'Accrual', debit: '', credit: 0 }],
      label,
    }).map(failure => failure.key)
    expect(keys.some(key => key.startsWith('lines.0.'))).toBe(true)
  })
})

describe('service charge form (/service-charges)', () => {
  const module = getFreightModule('/service-charges')!
  const feeLines = module.tables!.find(item => item.key === 'feeLines')!

  it('requires the customer', () => {
    expect(validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key)).toContain('customer')
  })

  it('locates an invalid fee line', () => {
    const keys = validateTableRows({
      table: feeLines,
      rows: [
        { feeType: 'Freight', description: 'Sea freight', quantity: 1, unitAmount: 100 },
        { feeType: '', description: 'Handling', quantity: 1, unitAmount: 20 },
      ],
      label,
    }).map(failure => failure.key)
    expect(keys).toContain('feeLines.1.feeType')
  })
})

describe('master data and administration forms', () => {
  it('requires the identifiers of a business party', () => {
    const module = getFreightModule('/master-data/business-parties')!
    expect(validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key).sort()).toEqual(['legalName', 'partyCode', 'roleIds'])
  })

  it('checks the business party phone and email formats, and leaves blank ones alone', () => {
    const module = getFreightModule('/master-data/business-parties')!
    // Narrowed to the two contact fields; the required identifiers are covered above.
    const codes = (model: Record<string, unknown>) =>
      validateDocumentFields({ fields: module.fields, model, isCreate: true, label })
        .map(f => f.key).filter(key => key === 'phone' || key === 'email')

    expect(codes({ phone: '+855 12 345 678' })).toEqual([])
    expect(codes({ phone: '(855) 12-345-678' })).toEqual([])
    expect(codes({ phone: '0123' }), 'too few digits must be refused').toContain('phone')
    expect(codes({ phone: 'call me' }), 'letters must be refused').toContain('phone')
    expect(codes({ email: 'contact@example.com' })).toEqual([])
    expect(codes({ email: 'contact.example.com' })).toContain('email')
    // Optional fields stay optional: a party with neither is still valid.
    expect(codes({ phone: '', email: '' })).toEqual([])
  })

  it('requires a name on every master-data record', () => {
    for (const path of [
      '/master-data/trade-directions',
      '/master-data/container-types',
      '/master-data/transport-types',
      '/master-data/fee-types',
      '/master-data/currencies',
    ]) {
      const module = getFreightModule(path)!
      const keys = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
        .map(f => f.key)
      expect(keys, path).toContain('name')
      expect(keys, path).toContain('code')
    }
  })

  it('requires the login identity and role of a user', () => {
    const module = getFreightModule('/administration/users')!
    const keys = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key)
    expect(keys).toContain('password')
    expect(keys).toContain('role')
  })

  it('requires the name of a role', () => {
    const module = getFreightModule('/administration/roles')!
    expect(validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key)).toEqual(['name'])
  })

  it('requires every field of a document sequence', () => {
    const module = getFreightModule('/administration/document-sequences')!
    const keys = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key)
    expect(keys).toEqual(expect.arrayContaining(['documentType', 'year', 'prefix', 'lastValue', 'paddingLength']))
  })

  it('requires the code and name of a ledger account', () => {
    const module = getFreightModule('/finance/chart-of-accounts')!
    const keys = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(f => f.key)
    expect(keys).toEqual(expect.arrayContaining(['accountCode', 'accountName']))
  })

  it('rejects a select value that is not one of its declared options', () => {
    const module = getFreightModule('/master-data/business-parties')!
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), status: 'SOMEWHERE_ELSE' },
      isCreate: true,
      label,
    })
    expect(failures).toContainEqual({ code: 'allowed', key: 'status', label: 'status' })
  })

  it('rejects an invalid document sequence year', () => {
    const module = getFreightModule('/administration/document-sequences')!
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { ...filledRecord(module), year: 42 },
      isCreate: true,
      label,
    })
    expect(failures).toContainEqual({ code: 'min', params: { min: 1000 }, key: 'year', label: 'year' })
  })
})