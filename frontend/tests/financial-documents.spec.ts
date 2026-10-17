/**
 * The Financial Documents module is document-type driven.
 *
 * What is pinned here:
 *
 * 1. the business party and the financial account come from Master Data and are
 *    stored as ids, so the form cannot invent a party;
 * 2. a line's account code is resolved from the posting rules — the column is
 *    read-only, and the derived value is stripped from the save payload so merely
 *    opening and saving a form cannot pin an account;
 * 3. the journal and the allocations are shown as the server recorded them, never
 *    edited in place;
 * 4. the status is not a form field at all — posting and reversal produce it, and
 *    the record menu runs them through the shared status manager;
 * 5. the labels say what the field is: a document date, not a quotation date, and
 *    a customer/supplier business party, not a company.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { referenceOptionSource } from '../app/utils/freight/reference-options'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const financeDocuments = getFreightModule('/finance/documents')!
const lines = financeDocuments.tables!.find(table => table.key === 'lines')!

describe('financial documents module', () => {
  it('takes the business party from Master Data as an id', () => {
    const field = financeDocuments.fields.find(item => item.key === 'partyId')

    expect(field?.required).toBe(true)
    expect(field?.type).toBe('select')
    expect(referenceOptionSource('partyId')).toMatchObject({
      collection: 'businessParties',
      valueField: 'id',
      labelField: 'legalName',
    })
  })

  it('takes the financial account from Master Data as an id', () => {
    expect(financeDocuments.fields.find(item => item.key === 'financialAccountId')?.type).toBe('select')
    expect(referenceOptionSource('financialAccountId')).toMatchObject({
      collection: 'financialAccounts',
      valueField: 'id',
    })
  })

  it('resolves a line account code from the posting rules instead of asking for one', () => {
    const column = lines.columns.find(item => item.key === 'accountCode')

    // Read-only: the account is what `post_document` will resolve for the line.
    expect(column?.computed).toBe(true)
    expect(column?.required).toBeUndefined()
    expect(column?.helpKey).toBe('freight.fieldHelp.accountCodeResolved')
  })

  it('strips the derived account code before saving', () => {
    const source = readFileSync(`${APP}/components/freight/DocumentView.vue`, 'utf8')

    expect(source).toContain("module.value.collection === 'debitNotes'")
    expect(source).toContain('delete next.accountCode')
  })

  it('shows the journal and the allocations as the server recorded them', () => {
    const tabs = moduleDocumentTabs(financeDocuments, { documentType: 'CUSTOMER_INVOICE', status: 'Posted' })
    const readOnly = (id: string) => tabs.find(tab => tab.id === id)?.sections[0]?.fields[0]?.readOnly

    expect(readOnly('journal')).toBe(true)
    expect(readOnly('allocation')).toBe(true)
  })

  it('keeps the status off the form: it is changed from the record menu', () => {
    // Posting and reversal produce the status, so no form field may write it.
    // The record page and the list both run the shared status manager, which
    // only offers transitions the backend policy allows.
    const tabs = moduleDocumentTabs(financeDocuments, { documentType: 'CUSTOMER_INVOICE' })
    const keys = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields.map(field => field.key)))
    expect(keys).not.toContain('status')

    const source = readFileSync(`${APP}/components/freight/DocumentView.vue`, 'utf8')
    expect(source).toContain('useRecordStatus')
    expect(source).not.toContain('setRecordStatus')
  })

  it('labels the document date and the business party for what they are', () => {
    const labelKey = (key: string) => financeDocuments.fields.find(item => item.key === key)?.labelKey

    expect(labelKey('date')).toBe('freight.fields.documentDate')
    expect(labelKey('partyId')).toBe('freight.fields.businessParty')
    expect(labelKey('debitNoteNo')).toBe('freight.fields.documentNo')
  })

  it('names the lines grid after this module rather than the journal', () => {
    expect(lines.title).toBe('Financial Lines')
    expect(lines.titleKey).toBe('freight.tables.financialLines')
  })
})
