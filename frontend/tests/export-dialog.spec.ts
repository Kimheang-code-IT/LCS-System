import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * The Export dialog is the single export entry point of the workspace list
 * pages: the header menu item only opens this dialog, which carries the
 * filters (date range, creator, status, search), the file format and the
 * scope — and disables Export while nothing matches.
 */
const dialog = readFileSync(resolve(__dirname, '../app/components/common/AppExportDialog.vue'), 'utf8')
const workspace = readFileSync(resolve(__dirname, '../app/components/freight/WorkspaceView.vue'), 'utf8')

describe('export dialog', () => {
  it('exposes the date-range, updated-by, status and format filters only', () => {
    for (const key of ['startDate', 'endDate', 'updatedBy', 'status', 'format', 'scope']) {
      expect(dialog).toContain(`const ${key}`)
    }
    // Created By and Search were removed from the dialog.
    for (const gone of ['createdBy = ref', 'const search = ref', 'lcs.exportDialog.createdBy', 'lcs.exportDialog.search']) {
      expect(dialog).not.toContain(gone)
    }
  })

  it('emits filters so the host can count matching records, and disables export on zero matches', () => {
    expect(dialog).toContain("'filters-change'")
    expect(dialog).toContain('noMatches')
    expect(dialog).toMatch(/canSubmit[^\n]*!noMatches/)
  })

  it('has a reset control that clears the filters without touching scope or format', () => {
    const reset = dialog.slice(dialog.indexOf('function resetFilters'), dialog.indexOf('watch(open'))
    expect(reset).toContain('startDate')
    expect(reset).toContain('updatedBy')
    expect(reset).not.toContain('format.value')
    expect(reset).not.toContain('scope.value')
    expect(dialog).toContain('resetFilters')
  })

  it('is opened by the single workspace Export menu item, which no longer downloads directly', () => {
    expect(workspace).toContain('exportOpen.value = true')
    expect(workspace).not.toContain('exportExcel()')
    expect(workspace).toContain('CommonAppExportDialog')
  })

  it('exports all matching records unless current page or selected rows is chosen', () => {
    expect(workspace).toMatch(/scope === 'selected'/)
    expect(workspace).toMatch(/scope === 'current_page'/)
  })
})
