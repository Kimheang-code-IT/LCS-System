import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Notification policy, enforced statically over the app sources.
 *
 * The rules are app-wide, so they are cheaper to assert by reading the code
 * than by mounting every form: a validation error must never be reported
 * through a toast, and a toast must never claim success before the request
 * that produced it has been confirmed.
 */

const APP_DIR = fileURLToPath(new URL('../app', import.meta.url))
const USE_API = join(APP_DIR, 'composables', 'useApi.ts')

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) sourceFiles(path, out)
    else if (/\.(ts|vue)$/.test(entry)) out.push(path)
  }
  return out
}

const SOURCES = sourceFiles(APP_DIR)
const relative = (path: string) => path.slice(APP_DIR.length + 1).replace(/\\/g, '/')

/** Every `toast.add({…})` / `toast({…})` literal in the app. */
function toastCalls(): Array<{ file: string, line: number, body: string }> {
  const calls: Array<{ file: string, line: number, body: string }> = []
  const pattern = /toast(?:\.add)?\(\s*\{/g
  for (const file of SOURCES) {
    const source = readFileSync(file, 'utf8')
    let match = pattern.exec(source)
    while (match) {
      const start = match.index
      let depth = 0
      let end = start
      for (let i = start; i < source.length; i++) {
        if (source[i] === '{') depth++
        else if (source[i] === '}') {
          depth--
          if (depth === 0) { end = i; break }
        }
      }
      calls.push({
        file: relative(file),
        line: source.slice(0, start).split('\n').length,
        body: source.slice(start, end + 1),
      })
      pattern.lastIndex = end
      match = pattern.exec(source)
    }
  }
  return calls
}

describe('toast notification policy', () => {
  it('never raises a toast for a validation or business-rule failure', () => {
    const offenders = toastCalls()
      .filter(call => /color:\s*'error'/.test(call.body))
      .filter(call => call.file !== 'composables/useApi.ts')
      .map(call => `${call.file}:${call.line}`)

    expect(offenders).toEqual([])
  })

  it('shows no "something went wrong" style toast from a form or page', () => {
    const offenders = toastCalls()
      .filter(call => /somethingWentWrong|saveFailed|couldNotSave/.test(call.body))
      // `useApi` is the transport layer, not a form: it keeps its own wording.
      .filter(call => call.file !== 'composables/useApi.ts')
      .map(call => `${call.file}:${call.line}`)

    expect(offenders).toEqual([])
  })

  it('keeps the global API toast for transport failures only', () => {
    const source = readFileSync(USE_API, 'utf8')
    // A 400/409/422 is rendered inline by the owning form, so the global
    // handler must not also notify for it.
    expect(source).toContain('isInlineValidationStatus')
    expect(source).toMatch(/isInlineValidationStatus\(response\.status\)/)
    expect(source).toMatch(/isInlineValidationStatus\(fetchError\.status/)
  })
})

describe('inline validation wiring', () => {
  const documentForm = readFileSync(join(APP_DIR, 'components', 'document', 'AppDocumentForm.vue'), 'utf8')
  const fieldRenderer = readFileSync(join(APP_DIR, 'components', 'document', 'AppDynamicFieldRenderer.vue'), 'utf8')
  const lineTable = readFileSync(join(APP_DIR, 'components', 'freight', 'AppLineTable.vue'), 'utf8')
  const documentPage = readFileSync(join(APP_DIR, 'components', 'document', 'AppDocumentPage.vue'), 'utf8')
  const documentView = readFileSync(join(APP_DIR, 'components', 'freight', 'DocumentView.vue'), 'utf8')
  const fieldGrid = readFileSync(join(APP_DIR, 'components', 'document', 'AppFieldGrid.vue'), 'utf8')

  it('tags every document field with its stable model path', () => {
    expect(documentForm).toContain(':data-field-key="field.key"')
  })

  it('renders the inline error on the shared form field wrapper', () => {
    // `UFormField` supplies aria-invalid / aria-describedby to the control.
    expect(fieldRenderer).toContain(':error="fieldError"')
    expect(fieldGrid).toContain(':error="errorFor(field)"')
  })

  it('renders a cell-level error inside the offending table cell', () => {
    expect(lineTable).toContain('cellErrorKey')
    expect(lineTable).toContain('data-slot')
  })

  it('shows an accessible error summary above the document form', () => {
    expect(documentPage).toContain('CommonAppFormErrorSummary')
    expect(documentPage).toContain('summaryItems')
    expect(documentPage).toContain('formErrors')
  })

  it('gates the save on client-side validation before calling the API', () => {
    const gate = documentView.indexOf('validation.applyFailures(failures)')
    const request = documentView.indexOf('documentActions.persistRecord(payload, isNew)')
    expect(gate).toBeGreaterThan(-1)
    expect(request).toBeGreaterThan(-1)
    expect(gate).toBeLessThan(request)
  })

  it('blocks a duplicate submission while a request is pending', () => {
    expect(documentView).toMatch(/if \(saving\.value\) return/)
  })

  it('routes a rejected request back through the shared mapping', () => {
    expect(documentView).toContain('validation.applyServerError(error)')
    expect(documentView).toContain('validation.focusFirstInvalid()')
  })
})