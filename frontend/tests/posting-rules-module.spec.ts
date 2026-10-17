import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FINANCIAL_DOCUMENT_STATUSES, FINANCIAL_DOCUMENT_TYPES } from '../app/config/freight-options'
import { lcsReferenceModules } from '../app/config/lcs-reference-modules'
import { referenceOptionSource, referenceSelectItems } from '../app/utils/freight/reference-options'
import { REMOTE_ENDPOINTS } from '../app/utils/api/freight-remote'
import { DOCUMENT_SEQUENCE_TYPES, documentSequenceTypeLabel } from '../app/utils/document-sequences'
import { ApiV1Endpoints } from '../app/utils/constants/api-v1-endpoints'
import * as documentTabs from '../app/utils/freight/document-tabs'

const PAGES = fileURLToPath(new URL('../app/pages', import.meta.url))
const COMPONENTS = fileURLToPath(new URL('../app/components', import.meta.url))

function pageSource(relative: string): string {
  return readFileSync(`${PAGES}/${relative}`, 'utf8')
}

function pagePath(relative: string): string {
  return `${PAGES}/${relative}`
}

function componentPath(folder: string, file: string): string {
  return `${COMPONENTS}/${folder}/${file}`
}

/**
 * The Posting Rules screen is configuration, not a bespoke page: it is a module
 * definition plus three reference sources. These tests pin the wiring, because
 * the failure mode of a metadata-driven form is a silently unpopulated select
 * rather than a visible error.
 */

const module = lcsReferenceModules.find(item => item.path === '/finance/posting-rules')!

describe('posting rules module', () => {
  it('is a standard module on the finance collection with its own page permission', () => {
    expect(module).toBeDefined()
    expect(module.collection).toBe('postingRules')
    expect(module.kind).toBe('standard')
    expect(module.permission).toBe('finance.posting_rules.view')
    expect(module.canCreate).toBe(true)
    expect(REMOTE_ENDPOINTS.postingRules.path).toBe('/api/v1/postingRules')
    expect(REMOTE_ENDPOINTS.postingRules.bulkDelete).toBe(true)
  })

  it('offers document type, accounts, priority and status', () => {
    const byKey = Object.fromEntries(module.fields.map(field => [field.key, field]))
    expect(Object.keys(byKey)).toEqual(
      expect.arrayContaining(['documentType', 'feeTypeId', 'debitAccount', 'creditAccount', 'taxAccount', 'priority', 'status']),
    )
    expect(byKey.documentType!.options).toEqual(FINANCIAL_DOCUMENT_TYPES)
    expect(byKey.documentType!.required).toBe(true)
    expect(byKey.debitAccount!.required).toBe(true)
    expect(byKey.creditAccount!.required).toBe(true)
    // Tax is optional: a rule with no tax posts the gross amount as one line.
    expect(byKey.taxAccount!.required).toBeFalsy()
    // Priority cannot be negative - the backend refuses it, so the form must too.
    expect(byKey.priority!.rule).toEqual({ min: 0 })
    expect(byKey.status!.options).toEqual(FINANCIAL_DOCUMENT_STATUSES)
  })

  it('lists rules with their accounts and priority so a misconfiguration is visible', () => {
    const keys = module.columns.map(column => column.key)
    expect(keys).toEqual(
      expect.arrayContaining(['documentTypeLabel', 'feeType', 'debitAccount', 'creditAccount', 'taxAccount', 'priority', 'status']),
    )
  })

  it('configures the document types the backend accepts, credit notes included', () => {
    // Mirrors DOCUMENT_TYPE_LABELS in backend/app/modules/finance/service.py;
    // a type missing on either side is refused at rule-configuration time.
    expect(FINANCIAL_DOCUMENT_TYPES).toEqual([
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
    ])
  })

  it('gives the two credit-note types a readable number prefix', () => {
    // `allocate_number` falls back to the first two characters of the type when
    // no sequence exists, which would number them "OT-000001" and "AD-000001".
    // The credit-note prefixes are declared so the numbers read as documents.
    for (const type of ['CREDIT_NOTE', 'SUPPLIER_CREDIT_NOTE']) {
      expect(DOCUMENT_SEQUENCE_TYPES as readonly string[]).toContain(type)
      expect(documentSequenceTypeLabel(type)).not.toBe(type)
    }
  })
})

describe('posting rule history is removed', () => {
  // The history screen was removed from the product at the owner's request. The
  // audit events behind it are still written and still visible in Audit Logs, so
  // these assertions protect the *removal* rather than the feature.
  it('has no history module definition or route', () => {
    expect(lcsReferenceModules.find(item => item.path === '/finance/posting-rules/history')).toBeUndefined()
    expect(REMOTE_ENDPOINTS.postingRuleHistory).toBeUndefined()
  })

  it('no longer ships the tab id, the component or the page', () => {
    expect('POSTING_RULE_HISTORY_TAB' in documentTabs).toBe(false)
    expect(existsSync(componentPath('freight', 'PostingRuleHistory.vue'))).toBe(false)
    expect(existsSync(pagePath('finance/posting-rules/history.vue'))).toBe(false)
  })

  it('does not reference the removed endpoints anywhere in the app', () => {
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_HISTORY')
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_RULE_HISTORY')
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_USAGE')
  })
})

describe('posting rule pages are wired to the right view', () => {
  // Getting this wrong is silent: the index route renders a blank form instead
  // of the list, and nothing fails until someone opens the page.
  it('uses the list view for the list, and the form view for a record', () => {
    expect(pageSource('finance/posting-rules/index.vue')).toContain('<FreightWorkspaceView />')
    expect(pageSource('finance/posting-rules/new.vue')).toContain('<FreightModulePage />')
    expect(pageSource('finance/posting-rules/[id].vue')).toContain('<FreightModulePage />')
  })

  it('matches the convention every other finance list page follows', () => {
    for (const path of ['finance/chart-of-accounts', 'finance/journals', 'finance/financial-accounts', 'finance/accounting-periods']) {
      expect(pageSource(`${path}/index.vue`)).toContain('<FreightWorkspaceView />')
    }
  })

  it('gates every posting rule page on the posting rule permission', () => {
    for (const file of ['index.vue', 'new.vue', '[id].vue']) {
      const source = pageSource(`finance/posting-rules/${file}`)
      expect(source).toContain("permission: 'finance.posting_rules.view'")
    }
  })
})

describe('posting rule reference selects', () => {
  const accounts = [
    { accountCode: '1100', accountName: 'Accounts Receivable', postable: true, status: 'ACTIVE' },
    { accountCode: '1900', accountName: 'Assets', postable: false, status: 'ACTIVE' },
    { accountCode: '1910', accountName: 'Retired asset', postable: true, status: 'INACTIVE' },
  ]

  it('offers only active, postable accounts and stores the account code', () => {
    for (const key of ['debitAccount', 'creditAccount', 'taxAccount']) {
      const source = referenceOptionSource(key)!
      expect(source.collection).toBe('chartOfAccounts')
      expect(source.valueField).toBe('accountCode')
      expect(referenceSelectItems(accounts, source)).toEqual([
        { label: 'Accounts Receivable', value: '1100' },
      ])
    }
  })

  it('resolves a fee type by id, because the backend stores its row id', () => {
    const source = referenceOptionSource('feeTypeId')!
    expect(source.collection).toBe('feeTypes')
    expect(source.valueField).toBe('id')
    expect(referenceSelectItems([{ id: '7', name: 'Freight', status: 'ACTIVE' }], source)).toEqual([
      { label: 'Freight', value: '7' },
    ])
  })

  it('leaves the fee type optional so a document default can be configured', () => {
    // A rule with no fee type is the fallback for the whole document type, which
    // is how most rules are written; an empty select must be a legal answer.
    const byKey = Object.fromEntries(module.fields.map(field => [field.key, field]))
    expect(byKey.feeTypeId!.required).toBeFalsy()
  })
})