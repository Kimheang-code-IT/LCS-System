import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { APP_LANGUAGES, APP_LANGUAGE_CODES, isAppLanguage, normalizeAppLanguages } from '../app/utils/constants/app-languages'

const LOCALES_DIR = fileURLToPath(new URL('../i18n/locales', import.meta.url))

type Messages = Record<string, unknown>

function loadLocale(code: string): Messages {
  return JSON.parse(readFileSync(`${LOCALES_DIR}/${code}.json`, 'utf8'))
}

/** Flatten nested message bundles to dotted key -> leaf value. */
function flatten(source: Messages, prefix = '', out: Record<string, string> = {}): Record<string, string> {
  for (const [key, value] of Object.entries(source)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) flatten(value as Messages, path, out)
    else out[path] = String(value)
  }
  return out
}

/** Interpolation tokens such as `{count}` that must survive translation. */
function placeholders(value: string): string[] {
  return [...new Set([...value.matchAll(/\{(\w+)\}/g)].map(match => match[1]!))].sort()
}

const en = loadLocale('en')
const flatEn = flatten(en)

describe('locale bundles', () => {
  it('ships one bundle per registered language', () => {
    for (const { code } of APP_LANGUAGES) {
      expect(() => loadLocale(code), `missing bundle for "${code}"`).not.toThrow()
    }
  })

  it.each(APP_LANGUAGE_CODES.filter(code => code !== 'en'))(
    'translates every English key in %s',
    (code) => {
      const flatTarget = flatten(loadLocale(code))
      const missing = Object.keys(flatEn).filter(key => !(key in flatTarget))
      expect(missing, `"${code}" is missing keys`).toEqual([])
    },
  )

  it.each(APP_LANGUAGE_CODES.filter(code => code !== 'en'))(
    'defines no keys that en.json does not have in %s',
    (code) => {
      const flatTarget = flatten(loadLocale(code))
      const orphans = Object.keys(flatTarget).filter(key => !(key in flatEn))
      expect(orphans, `"${code}" has keys absent from en.json`).toEqual([])
    },
  )

  it.each(APP_LANGUAGE_CODES)('keeps interpolation tokens intact in %s', (code) => {
    const flatTarget = flatten(loadLocale(code))
    const broken = Object.keys(flatEn)
      .filter(key => key in flatTarget)
      .filter(key => placeholders(flatTarget[key]!).join('|') !== placeholders(flatEn[key]!).join('|'))
    expect(broken, `"${code}" changed a placeholder`).toEqual([])
  })

  it.each(APP_LANGUAGE_CODES.filter(code => code !== 'en'))(
    'actually translates %s rather than copying English',
    (code) => {
      const flatTarget = flatten(loadLocale(code))
      // Codes, brand names and pure placeholder strings are legitimately identical.
      const identical = Object.keys(flatEn)
        .filter(key => key in flatTarget && flatTarget[key] === flatEn[key])
        .filter(key => /[A-Za-z]{4,}/.test(flatEn[key]!) && !/\{\w+\}/.test(flatEn[key]!))
      expect(identical.length / Object.keys(flatEn).length).toBeLessThan(0.05)
    },
  )
})

describe('language registry', () => {
  it('normalizes and guards language codes', () => {
    expect(isAppLanguage('zh')).toBe(true)
    expect(isAppLanguage('en')).toBe(true)
    expect(isAppLanguage('km')).toBe(true)
    expect(isAppLanguage('zz')).toBe(false)
    expect(isAppLanguage(undefined)).toBe(false)
  })

  it('drops unsupported codes and duplicates while preserving order', () => {
    expect(normalizeAppLanguages(['zh', 'zz', 'en', 'zh'])).toEqual(['zh', 'en'])
    expect(normalizeAppLanguages('not-an-array')).toEqual([])
  })

  it('gives every language a distinct BCP-47 locale', () => {
    const locales = APP_LANGUAGES.map(language => language.locale)
    expect(new Set(locales).size).toBe(locales.length)
  })
})