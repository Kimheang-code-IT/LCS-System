import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const read = (path: string) => readFileSync(`${APP}/${path}`, 'utf8')

describe('document form draft integration', () => {
  it('quotation, charge and finance document forms use the shared draft composable', () => {
    const view = read('components/freight/DocumentView.vue')
    expect(view).toContain('useRecordFormDraft')
    expect(view).toContain("new Set(['quotations', 'jobCharges', 'debitNotes', 'journals'])")
    expect(view).toContain('restoreFormDraft()')
    expect(view).toContain('formDraft.clear()')
    expect(view).toContain('<CommonAppDraftConflictAlert')
    // Clearing happens only after the save promise resolved.
    expect(view.indexOf('formDraft.clear()')).toBeGreaterThan(view.indexOf('await documentActions.persistRecord'))
  })

  it('service order drafts include dynamic component rows and the shared alert', () => {
    const detail = read('components/freight/JobDetail.vue')
    expect(detail).toContain('useRecordFormDraft')
    expect(detail).toContain('componentRows')
    expect(detail).toContain('captureComponentBaseline')
    expect(detail).toContain('<CommonAppDraftConflictAlert')
    expect(detail).toContain('formDraft.clear()')
    // The old hand-rolled draft writer is gone.
    expect(detail).not.toContain('persistPageDraft')
    expect(detail).not.toContain('draftTimer')
  })

  it('service charge drafts key a new charge by its stable client marker', () => {
    const charges = read('components/freight/JobCharges.vue')
    expect(charges).toContain('useRecordFormDraft')
    expect(charges).toContain('serviceChargeDraftRecordId')
    expect(charges).toContain('readRecordDraftsByPrefix')
    expect(charges).toContain('<CommonAppDraftConflictAlert')
    expect(charges).not.toContain('persistDraftNow')
  })

  it('finance entries use the shared draft layer and keep posted rows server-owned', () => {
    const finance = read('components/freight/JobFinance.vue')
    expect(finance).toContain('useRecordFormDraft')
    expect(finance).toContain('mergeFinanceDraftRows')
    expect(finance).toContain('formDraft.restore()')
    expect(finance).not.toContain('persistFinanceDraft')
  })

  it('route and file tabs no longer write the whole order per keystroke', () => {
    expect(read('components/freight/JobRoute.vue')).not.toContain("store.save('jobs'")
    expect(read('components/freight/JobFiles.vue')).not.toContain("store.save('jobs'")
  })

  it('container edits use the single-flight autosave and flush on navigation', () => {
    const containers = read('components/freight/JobContainers.vue')
    expect(containers).toContain('useAutosave')
    expect(containers).toContain('autosave.flush()')
    expect(containers).toContain('persistForPrint')
    // The whole-order write survives only on the explicit print path.
    expect(containers.match(/store\.save\('jobs'/g)).toHaveLength(1)
  })

  it('purges the signed-in user drafts when the session is cleared', () => {
    expect(read('stores/auth.ts')).toContain('clearRecordDraftsForUser')
  })

  it('keeps the shared editable table free of page-specific draft logic', () => {
    const table = read('components/freight/AppLineTable.vue')
    expect(table).not.toContain('useRecordFormDraft')
    expect(table).not.toContain('serviceChargeFormPayload')
  })
})
