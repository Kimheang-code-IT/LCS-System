import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { fieldErrorMessage, formFieldError } from '../app/utils/validation/form-field-error'

/**
 * `UFormField.error` is declared `[Boolean, String]`. Vue casts an empty string
 * to `true` when Boolean sits before String in the type array, so a field that
 * has **no** error but receives `''` renders with the error ring/outline and
 * `aria-invalid="true"` (no message is shown, because a Boolean error has no
 * text). That is the "every field is red" bug on the Service Order Overview.
 *
 * "No error" must therefore be `undefined` — asserted here both on the shared
 * normalisers and statically on every `:error` binding in the app.
 */

const APP_DIR = fileURLToPath(new URL('../app', import.meta.url))

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

function readAppFile(...segments: string[]): string {
  return readFileSync(join(APP_DIR, ...segments), 'utf8')
}

describe('form field error normalisation', () => {
  it('returns the message for a field that failed', () => {
    expect(formFieldError({ company: 'Company is required.' }, 'company')).toBe('Company is required.')
  })

  it('returns undefined — never an empty string — when the field has no error', () => {
    expect(formFieldError({}, 'company')).toBeUndefined()
    expect(formFieldError({ company: '' }, 'company')).toBeUndefined()
    expect(formFieldError(undefined, 'company')).toBeUndefined()
    expect(formFieldError(null, 'company')).toBeUndefined()
  })

  it('normalises a message held in its own ref the same way', () => {
    expect(fieldErrorMessage('Only PNG or JPEG images are allowed.')).toBe('Only PNG or JPEG images are allowed.')
    expect(fieldErrorMessage('')).toBeUndefined()
    expect(fieldErrorMessage(undefined)).toBeUndefined()
    expect(fieldErrorMessage(null)).toBeUndefined()
  })
})

describe(':error bindings', () => {
  it('never falls back to an empty string', () => {
    const bindings = /:error="([^"]*)"/g
    const offenders: string[] = []
    for (const file of SOURCES) {
      const source = readFileSync(file, 'utf8')
      let match = bindings.exec(source)
      while (match) {
        if (/\|\|\s*(''|"")/.test(match[1] ?? '')) {
          offenders.push(`${relative(file)}: ${match[0]}`)
        }
        match = bindings.exec(source)
      }
      bindings.lastIndex = 0
    }
    expect(offenders).toEqual([])
  })

  it('routes every renderer that owns a field-error map through the shared normaliser', () => {
    // These render a `fieldErrors` map keyed by model path; an empty value for
    // a clean field must not reach `UFormField.error`.
    expect(readAppFile('components', 'document', 'AppFieldGrid.vue')).toContain('formFieldError(props.fieldErrors')
    expect(readAppFile('components', 'document', 'AppComponentTabs.vue')).toContain('formFieldError(props.fieldErrors')
    expect(readAppFile('components', 'document', 'AppDynamicFieldRenderer.vue')).toContain('formFieldError(props.fieldErrors')

    // These hold their message in a plain ref that starts as `''`.
    expect(readAppFile('components', 'common', 'AppImageUploadField.vue')).toContain('fieldErrorMessage(fileError)')
    expect(readAppFile('pages', 'auth', 'verify-code.vue')).toContain('fieldErrorMessage(formError)')
  })
})
