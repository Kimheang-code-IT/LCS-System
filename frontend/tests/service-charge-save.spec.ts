import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const read = (path: string) => readFileSync(`${APP}/${path}`, 'utf8')

const charges = read('components/freight/JobCharges.vue')
const sharedForm = read('components/freight/ServiceChargeForm.vue')
const detail = read('components/freight/JobDetail.vue')
const standalone = read('components/freight/DocumentView.vue')
const formModel = read('utils/freight/service-charge-form.ts')

describe('shared service charge form', () => {
  it('renders the standalone page and the Service Order tab through one component', () => {
    // Standalone Service Charge page.
    expect(standalone).toContain('<FreightServiceChargeForm')
    expect(standalone).toContain("module.collection === 'jobCharges'")
    // Embedded tab.
    expect(charges).toContain('<FreightServiceChargeForm')
    // The component is the existing config-driven document form, not a copy.
    expect(sharedForm).toContain('DocumentAppDocumentForm')
    expect(sharedForm).toContain('SERVICE_CHARGE_MODULE_PATH')
    expect(sharedForm).toContain('recalculateFreightRecord')
    expect(sharedForm).toContain('validateDocumentFields')
    expect(sharedForm).toContain('validateTableRows')
  })

  it('keeps the same tabs, fee lines and totals in both hosts', () => {
    expect(formModel).toContain('serviceChargeFormTabs')
    expect(formModel).toContain('moduleDocumentTabs')
    expect(formModel).toContain("tab.id !== 'traceability'")
    expect(formModel).toContain('serviceChargeFormPayload')
    expect(sharedForm).toContain('feeLines')
    expect(sharedForm).toContain('payload')
  })

  it('has its own save boundary — the page save never touches charges', () => {
    expect(charges).toContain('async function save()')
    expect(charges).toContain('createForOrder')
    expect(charges).toContain('saveDraft')
    expect(detail).not.toContain('chargesTab.value?.savePending()')
    expect(detail).toContain('never creates or posts one')
    // The page save still exists and only writes the order.
    expect(detail).toContain('moduleRecord.update')
  })

  it('prevents duplicate creation from repeated clicks or a lost response', () => {
    expect(charges).toContain('saving.value || !canEditCurrent.value')
    expect(charges).toContain('clientRowId')
    expect(charges).toContain('charges.value.find')
    expect(formModel).toContain('createClientId')
    expect(formModel).toContain('clientRowId')
  })

  it('keeps its editable state across tab switches and refreshes', () => {
    expect(detail).toContain("v-if=\"chargesVisited\" v-show=\"activeTab === 'charges'\"")
    expect(charges).toContain('useRecordFormDraft')
    expect(charges).toContain('formDraft.restore')
    expect(charges).toContain('formDraft.conflict')
    expect(charges).toContain('formDraft.clear')
  })
})
