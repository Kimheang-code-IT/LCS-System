#!/usr/bin/env node
/**
 * Locale bundle maintenance helper.
 *
 *   node scripts/i18n.mjs check              # locale parity + placeholder audit
 *   node scripts/i18n.mjs add <file> <json>  # deep-merge a JSON patch into a locale
 *   node scripts/i18n.mjs missing <file>     # keys present in en.json but absent here
 *   node scripts/i18n.mjs orphan <file>      # keys here that en.json does not define
 *
 * Every locale under i18n/locales must stay structurally identical to en.json so
 * no screen can silently fall back to English at runtime.
 */
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const LOCALES_DIR = join(process.cwd(), 'i18n', 'locales')
const SOURCE = 'en'

function localeFiles() {
  return readdirSync(LOCALES_DIR)
    .filter(name => name.endsWith('.json'))
    .map(name => name.replace(/\.json$/, ''))
    .sort()
}

function load(code) {
  return JSON.parse(readFileSync(join(LOCALES_DIR, `${code}.json`), 'utf8'))
}

function save(code, data) {
  writeFileSync(join(LOCALES_DIR, `${code}.json`), `${JSON.stringify(data, null, 2)}\n`, 'utf8')
}

/** Flatten to dotted key -> leaf value. */
function flat(value, prefix = '', out = {}) {
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (child && typeof child === 'object' && !Array.isArray(child)) flat(child, path, out)
    else out[path] = child
  }
  return out
}

/** Interpolation tokens such as {name} / {count}, used to audit copy integrity. */
function placeholders(value) {
  return typeof value === 'string' ? [...value.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort() : []
}

/**
 * True when `target` keeps every interpolation token the source declares.
 * Vue-i18n plural sources ("one | many") legitimately collapse to a single
 * variant, so the tokens are compared against the source union instead.
 */
function placeholdersMatch(source, target) {
  const sourceTokens = [...new Set(placeholders(source))].sort()
  const targetTokens = [...new Set(placeholders(target))].sort()
  return sourceTokens.join('|') === targetTokens.join('|')
}

function isObject(value) {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

function deepMerge(target, patch) {
  for (const [key, value] of Object.entries(patch)) {
    if (isObject(value)) target[key] = deepMerge(isObject(target[key]) ? target[key] : {}, value)
    else target[key] = value
  }
  return target
}

function deepAssign(target, source) {
  for (const [key, value] of Object.entries(source)) {
    if (isObject(value)) target[key] = deepAssign(isObject(target[key]) ? target[key] : {}, value)
    else target[key] = value
  }
  return target
}

const commands = {
  check() {
    const source = flat(load(SOURCE))
    const sourceKeys = Object.keys(source)
    let failed = false

    for (const code of localeFiles()) {
      if (code === SOURCE) continue
      const target = flat(load(code))
      const targetKeys = Object.keys(target)
      const missingKeys = sourceKeys.filter(key => !(key in target))
      const orphanKeys = targetKeys.filter(key => !(key in source))
      const untranslated = sourceKeys.filter(key => key in target && target[key] === source[key])
      const badPlaceholders = sourceKeys.filter(key => {
        if (!(key in target)) return false
        return !placeholdersMatch(source[key], target[key])
      })

      const report = (label, list) => {
        if (!list.length) return
        failed = true
        console.log(`  ${label} (${list.length}):`)
        for (const key of list.slice(0, 40)) console.log(`    - ${key}`)
        if (list.length > 40) console.log(`    ... ${list.length - 40} more`)
      }

      console.log(`[${code}] ${targetKeys.length}/${sourceKeys.length} keys`)
      report('missing', missingKeys)
      report('orphaned (not in en)', orphanKeys)
      report('placeholder mismatch', badPlaceholders)
      if (untranslated.length && code !== 'km') {
        console.log(`  identical to English (${untranslated.length}) - untranslated`)
      }
    }

    if (failed) {
      console.error('\nLocale check FAILED')
      process.exitCode = 1
      return
    }
    console.log('\nLocale check passed')
  },

  missing(code) {
    const source = flat(load(SOURCE))
    const target = flat(load(code))
    for (const key of Object.keys(source)) {
      if (!(key in target)) console.log(`${key}\t${JSON.stringify(source[key])}`)
    }
  },

  orphan(code) {
    const source = flat(load(SOURCE))
    const target = flat(load(code))
    for (const key of Object.keys(target)) {
      if (!(key in source)) console.log(`${key}\t${JSON.stringify(target[key])}`)
    }
  },

  add(code, patch) {
    if (!code || !patch) {
      console.error('Usage: node scripts/i18n.mjs add <locale> \'{"ns":{"key":"Value"}}\'')
      process.exitCode = 1
      return
    }
    const data = load(code)
    deepMerge(data, JSON.parse(patch))
    save(code, data)
    console.log(`Updated ${code}.json`)
  },

  /** Rebuild a locale from the source skeleton, keeping existing translations. */
  resync(code) {
    const data = load(code)
    const before = flat(data)
    const rebuilt = deepAssign(load(SOURCE), data)
    const after = flat(rebuilt)
    const added = Object.keys(after).filter(key => !(key in before))
    save(code, rebuilt)
    console.log(`Resynced ${code}.json (${added.length} keys added, ${Object.keys(after).length} total)`)
  },

  /** Remove a dotted key from one locale, or from every locale when code is `all`. */
  rm(code, dottedKey) {
    if (!dottedKey) {
      console.error('Usage: node scripts/i18n.mjs rm <locale|all> <dotted.key>')
      process.exitCode = 1
      return
    }
    const targets = code === 'all' ? localeFiles() : [code]
    const parts = dottedKey.split('.')
    for (const target of targets) {
      const data = load(target)
      let node = data
      for (const part of parts.slice(0, -1)) {
        node = node?.[part]
        if (!isObject(node)) break
      }
      const leaf = parts[parts.length - 1]
      if (isObject(node) && leaf in node) {
        delete node[leaf]
        save(target, data)
        console.log(`Removed ${dottedKey} from ${target}.json`)
      }
      else {
        console.log(`Not present: ${dottedKey} in ${target}.json`)
      }
    }
  },
}

const [command, ...args] = process.argv.slice(2)
if (!commands[command]) {
  console.error(`Unknown command: ${command ?? '(none)'}`)
  console.error(`Available: ${Object.keys(commands).join(', ')}`)
  process.exitCode = 1
}
else {
  commands[command](...args)
}