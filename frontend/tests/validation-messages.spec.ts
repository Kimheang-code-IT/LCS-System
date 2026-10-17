import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { ISSUE_KEYS } from '../app/utils/validation/messages'

/**
 * Every message the shared validation stack can render must exist in every
 * shipped locale, otherwise a validation failure silently falls back to the raw
 * key. This is the failure mode the locale audit does not catch: it only knows
 * about keys that are *present*, not about keys that are *referenced*.
 */

const LOCALES = ['en', 'km', 'zh']
const read = (code: string) => JSON.parse(
  readFileSync(fileURLToPath(new URL(`../i18n/locales/${code}.json`, import.meta.url)), 'utf8'),
)

const bundles = new Map(LOCALES.map(code => [code, read(code)]))

function lookup(bundle: Record<string, unknown>, dotted: string): unknown {
  return dotted.split('.').reduce<unknown>((node, part) => {
    if (node && typeof node === 'object') return (node as Record<string, unknown>)[part]
    return undefined
  }, bundle)
}

const usedKeys = [
  ...Object.values(ISSUE_KEYS).flatMap(key => [key, ...(key === 'validation.balanced' ? [] : [`${key}Generic`])]),
  'validation.summaryTitle',
  'validation.summaryCount',
  'validation.formError',
  'validation.minRows',
  'validation.duplicateSequence',
  'validation.rowCell',
]

describe('validation message bundle', () => {
  it('declares a message and a label-free variant for every issue code', () => {
    for (const code of Object.values(ISSUE_KEYS)) {
      expect(usedKeys, code).toContain(code)
      // `balanced` states the rule, so it is the one code without a variant.
      if (code === 'validation.balanced') continue
      expect(usedKeys, code).toContain(`${code}Generic`)
    }
  })

  it('ships every validation key in every locale', () => {
    const missing: string[] = []
    for (const code of LOCALES) {
      const bundle = bundles.get(code)!
      for (const key of usedKeys) {
        if (lookup(bundle, key) === undefined) missing.push(`${code}:${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  it('keeps every placeholder present in every locale', () => {
    const english = bundles.get('en') as Record<string, unknown>
    const problems: string[] = []
    for (const code of LOCALES.filter(item => item !== 'en')) {
      const bundle = bundles.get(code)!
      for (const key of usedKeys) {
        const source = String(lookup(english, key) ?? '')
        const target = String(lookup(bundle, key) ?? '')
        const sourceTokens = [...source.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort()
        const targetTokens = [...target.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort()
        if (sourceTokens.join('|') !== targetTokens.join('|')) problems.push(`${code}:${key}`)
      }
    }
    expect(problems).toEqual([])
  })

  it('never renders a message that mentions an internal key or status code', () => {
    const english = bundles.get('en') as Record<string, unknown>
    for (const key of usedKeys) {
      const message = String(lookup(english, key) ?? '')
      expect(message, key).not.toMatch(/\b(422|400|409|500|loc|detail|traceback|null|undefined)\b/i)
    }
  })
})