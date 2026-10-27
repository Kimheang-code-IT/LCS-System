import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const workspace = readFileSync(resolve(__dirname, '../app/components/freight/WorkspaceView.vue'), 'utf8')
const dialog = readFileSync(resolve(__dirname, '../app/components/excel/ImportExportDialog.vue'), 'utf8')
const client = readFileSync(resolve(__dirname, '../app/composables/useExcelIo.ts'), 'utf8')

describe('Excel import/export wiring', () => {
  it('list pages host the shared dialog and offer import/export from the header menu', () => {
    expect(workspace).toContain('ExcelImportExportDialog')
    expect(workspace).toContain('headerMenuItems')
    expect(workspace).toContain('excelModule')
    // The actions are header ⋯ menu items, not table-toolbar buttons.
    expect(workspace).toMatch(/onSelect: \(\) => \{ importOpen\.value = true \}/)
    expect(workspace).toContain("t('freight.excel.import')")
  })

  it('keeps the New button in the header while Import/Export stay in the menu', () => {
    // Creating is a primary action; import/export moved off the table toolbar.
    expect(workspace).toContain(':can-create="canCreate"')
    expect(workspace).toContain('@create="openCreate"')
    expect(workspace).not.toContain('excelExportLabel }}</UButton>')
    expect(workspace).toContain(':empty-actions="canCreate')
  })

  it('the import dialog drives the template → validate → confirm workflow', () => {
    expect(dialog).toContain('api.template(')
    expect(dialog).toContain('api.validate(')
    expect(dialog).toContain('api.commit(')
    expect(dialog).toContain('api.cancel(')
    expect(dialog).toContain('api.errorReport(')
  })

  it('opening the dialog from the menu loads the import history', () => {
    expect(dialog).toContain('defineModel<boolean>(\'open\'')
    expect(dialog).toContain('watch(open')
    expect(dialog).toContain('api.history(props.collection)')
  })

  it('import needs the manage permission while export only needs view', () => {
    // Import mutates master data; export is available to view-only users.
    expect(workspace).toContain('lcs.can(module_.managePermission as never)')
    expect(workspace).toContain('lcs.can(module_.viewPermission as never)')
    expect(dialog).not.toContain('canManageImport')
  })

  it('the client never posts cross-origin and only uploads .xlsx', () => {
    expect(client).toContain('sameOriginApiUrl')
    expect(client).toContain("'POST'")
    const router = readFileSync(resolve(__dirname, '../../backend/app/modules/excel_io/router.py'), 'utf8')
    expect(router).toContain(".xlsx")
    expect(router).toContain('MAX_FILE_BYTES')
  })

  it('the export request declares a JSON body', () => {
    // FastAPI rejects a JSON string body sent as text/plain with a 422.
    const exportCall = client.slice(client.indexOf('exportRows'))
    expect(exportCall).toContain("'Content-Type': 'application/json'")
  })

  it('the backend template column keys stay language-independent', () => {
    const templatesSource = readFileSync(resolve(__dirname, '../../backend/app/modules/excel_io/templates.py'), 'utf8')
    expect(templatesSource).toContain('TEMPLATE_VERSION')
    const registry = readFileSync(resolve(__dirname, '../../backend/app/modules/excel_io/registry.py'), 'utf8')
    expect(registry).toContain('businessParties')
    expect(registry).toContain('documentTypes')
  })
})
