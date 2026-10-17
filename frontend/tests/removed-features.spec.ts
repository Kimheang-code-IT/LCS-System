/**
 * The removals are complete and stay complete.
 *
 *  - **Posting Rule History**, including the rule detail's History tab. The audit
 *    events behind it are still written and still visible in Audit Logs; only the
 *    dedicated screens and endpoints went away.
 *
 * The FX-rate editor was the second subject of this file. It was removed, and then
 * deliberately reinstated: the owner asked for exchange rates to be *consumed*, so
 * documents resolve, validate and store the rate they convert at. What is asserted
 * here is the part of that removal that must survive — the currency master every
 * currency dropdown reads, and the old pair select keys, which the reinstated store
 * does not use (`fromCurrencyCode`/`toCurrencyCode` instead). The store's own
 * wiring is asserted positively in `tests/multi-currency.spec.ts`.
 *
 * A half-finished removal is the real risk — a menu link to a deleted page, a
 * module definition with no page, or a call to a deleted endpoint — so these tests
 * check every layer the features used to touch.
 */
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { lcsReferenceModules } from '../app/config/lcs-reference-modules'
import { REMOTE_ENDPOINTS, endpointFor } from '../app/utils/api/freight-remote'
import { ApiV1Endpoints } from '../app/utils/constants/api-v1-endpoints'
import { referenceOptionSource, referenceSelectItems } from '../app/utils/freight/reference-options'
import * as documentTabs from '../app/utils/freight/document-tabs'

const PAGES = fileURLToPath(new URL('../app/pages', import.meta.url))
const COMPONENTS = fileURLToPath(new URL('../app/components', import.meta.url))
const MENU = fileURLToPath(new URL('../app/composables/layout/useMenu.ts', import.meta.url))

const menuSource = readFileSync(MENU, 'utf8')

describe('currency master survives the FX changes', () => {
  it('kept the currency master that every currency dropdown reads', () => {
    // Removing, and later reinstating, the rates table must never take the
    // currencies with it: every currency select resolves through this collection.
    expect(REMOTE_ENDPOINTS.currencies).toBeDefined()
    expect(endpointFor('currencies')?.path).toBe('/api/v1/currencies')
    expect(lcsReferenceModules.some(item => item.path === '/master-data/currencies')).toBe(true)

    const currencySelects = ['currency', 'currency20', 'currency40', 'currency45']
    for (const key of currencySelects) {
      expect(referenceOptionSource(key)?.collection, `${key} must still read the currency master`).toBe(
        'currencies',
      )
    }

    expect(
      referenceSelectItems(
        [
          { id: '1', code: 'USD', name: 'US Dollar', status: 'ACTIVE' },
          { id: '2', code: 'KHR', name: 'Cambodian Riel', status: 'ACTIVE' },
        ],
        referenceOptionSource('currency')!,
      ),
    ).toEqual([
      { label: 'US Dollar', value: 'USD' },
      { label: 'Cambodian Riel', value: 'KHR' },
    ])
  })

  it('did not bring the old pair select keys back', () => {
    // These key names belonged to the removed editor; the reinstated store uses
    // `fromCurrencyCode`/`toCurrencyCode`, so the old ones stay gone for good.
    expect(referenceOptionSource('fromCurrency')).toBeUndefined()
    expect(referenceOptionSource('toCurrency')).toBeUndefined()
  })
})

describe('posting rule history removal', () => {
  it('has no module definition, route or menu link', () => {
    expect(lcsReferenceModules.find(item => item.path === '/finance/posting-rules/history')).toBeUndefined()
    expect(menuSource).not.toContain('posting-rules/history')
    expect(menuSource).not.toContain('freight.pages.postingRuleHistory')
  })

  it('has no page or component files left behind', () => {
    expect(existsSync(`${PAGES}/finance/posting-rules/history.vue`)).toBe(false)
    expect(existsSync(`${COMPONENTS}/freight/PostingRuleHistory.vue`)).toBe(false)
  })

  it('no longer exports the document-view tab id', () => {
    expect('POSTING_RULE_HISTORY_TAB' in documentTabs).toBe(false)
  })

  it('no longer exposes the history endpoints', () => {
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_HISTORY')
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_RULE_HISTORY')
    expect(ApiV1Endpoints).not.toHaveProperty('POSTING_RULE_USAGE')
    expect(REMOTE_ENDPOINTS.postingRuleHistory).toBeUndefined()
  })

  it('kept the posting rules screen and its account selects', () => {
    const postingRules = lcsReferenceModules.find(item => item.path === '/finance/posting-rules')
    expect(postingRules).toBeDefined()
    expect(postingRules?.collection).toBe('postingRules')
    // The engine depends on these account mappings; only history was removed.
    expect(referenceOptionSource('debitAccount')?.collection).toBe('chartOfAccounts')
    expect(referenceOptionSource('creditAccount')?.collection).toBe('chartOfAccounts')
  })

  it('kept the priority field, which drives rule resolution', () => {
    const postingRules = lcsReferenceModules.find(item => item.path === '/finance/posting-rules')
    const keys = postingRules!.fields.map(field => field.key)
    expect(keys).toContain('priority')
  })
})
