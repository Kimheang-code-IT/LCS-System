/**
 * The navigation menu must be fully translatable.
 *
 * A real defect motivated this guard: two group headers in `useMenu.ts` were
 * bare English literals (`'Operations Reports'`, `'Financial Reports'`) while
 * every other entry resolved through `t(...)`. In a Chinese or Khmer session
 * those two headers stayed English, and a missing key rendered as its own raw
 * path (`freight.pages.postingRu…`) instead of a label.
 *
 * Three rules are enforced:
 *   1. every `t('key')` the menu references exists in the bundles;
 *   2. no position that holds a user-visible label takes a bare string literal;
 *   3. the two nav group keys added for this fix resolve in all three locales.
 *
 * Parity across locales is separately guaranteed by `tests/i18n-locales.spec.ts`,
 * so checking `en` is enough for rule 1.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { APP_LANGUAGE_CODES } from '../app/utils/constants/app-languages'

const MENU = fileURLToPath(
  new URL('../app/composables/layout/useMenu.ts', import.meta.url),
)
const LOCALES_DIR = fileURLToPath(new URL('../i18n/locales', import.meta.url))

const menuSource = readFileSync(MENU, 'utf8')

function flatten(source: Record<string, unknown>, prefix = '', out: Record<string, unknown> = {}) {
  for (const [key, value] of Object.entries(source)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      flatten(value as Record<string, unknown>, path, out)
    }
    else {
      out[path] = value
    }
  }
  return out
}

function loadFlat(code: string): Record<string, unknown> {
  return flatten(JSON.parse(readFileSync(`${LOCALES_DIR}/${code}.json`, 'utf8')))
}

const flatEn = loadFlat('en')

/** Every `t('...')` key the menu asks vue-i18n for. */
function referencedKeys(): string[] {
  const keys = new Set<string>()
  for (const match of menuSource.matchAll(/\bt\(\s*'([^']+)'\s*\)/g)) keys.add(match[1]!)
  return [...keys].sort()
}

/** Strip comments so a commented-out example cannot fail the label rules. */
function codeOnly(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ \t]*\/\/.*$/gm, '')
}

describe('navigation menu internationalisation', () => {
  it('references i18n keys only when they exist', () => {
    const missing = referencedKeys().filter(key => flatEn[key] === undefined)
    expect(missing, `menu references keys missing from the bundles: ${missing.join(', ')}`).toEqual([])
  })

  it('never passes a bare string literal as a group header', () => {
    // group(id, label, icon, children) — the label is the second argument.
    const offenders: string[] = []
    for (const match of codeOnly(menuSource).matchAll(/\bgroup\(\s*'([^']*)'\s*,\s*([^,]+),/g)) {
      const label = match[2]!.trim()
      if (/^['"`]/.test(label)) offenders.push(`group('${match[1]}') label = ${label}`)
    }
    expect(offenders, `hardcoded group header(s): ${offenders.join(' | ')}`).toEqual([])
  })

  it('never passes a bare string literal as a page link label', () => {
    // pageLink(label, to) — the label is the first argument.
    const offenders: string[] = []
    for (const match of codeOnly(menuSource).matchAll(/\bpageLink\(\s*([^,]+),/g)) {
      const label = match[1]!.trim()
      if (/^['"`]/.test(label)) offenders.push(`pageLink label = ${label}`)
    }
    expect(offenders, `hardcoded page label(s): ${offenders.join(' | ')}`).toEqual([])
  })

  it('never assigns a bare string literal to a label property', () => {
    const offenders = [...codeOnly(menuSource).matchAll(/\blabel:\s*(['"`])([^'"`]*)\1/g)].map(
      match => `label: ${match[2]}`,
    )
    expect(offenders, `hardcoded label(s): ${offenders.join(' | ')}`).toEqual([])
  })

  it('resolves the report group headers in every supported locale', () => {
    for (const code of APP_LANGUAGE_CODES) {
      const flat = loadFlat(code)
      for (const key of ['freight.nav.operationsReports', 'freight.nav.financialReports']) {
        const value = flat[key]
        expect(typeof value, `${code} is missing ${key}`).toBe('string')
        expect(String(value).trim(), `${code}.${key} is blank`).not.toBe('')
      }
    }
  })

  it('translates the report group headers rather than echoing English', () => {
    const en = loadFlat('en')
    // These two were English-only literals before the fix; a locale that still
    // returns the English copy means the translation was never added.
    const expectedDiffer = ['km', 'zh']
    for (const code of expectedDiffer) {
      const flat = loadFlat(code)
      expect(
        flat['freight.nav.operationsReports'],
        `${code} still shows the English "Operations Reports"`,
      ).not.toBe(en['freight.nav.operationsReports'])
      expect(
        flat['freight.nav.financialReports'],
        `${code} still shows the English "Financial Reports"`,
      ).not.toBe(en['freight.nav.financialReports'])
    }
  })
})
