#!/usr/bin/env node
/**
 * Map a git diff to the feature groups in docs/12_feature_status.md.
 *
 * Read-only by design: it prints which rows to re-verify. It never edits the
 * report and never decides a status — tests and live checks do that.
 *
 * Usage (from the repository root):
 *   node scripts/feature-status.mjs                      # working tree vs HEAD
 *   node scripts/feature-status.mjs --base origin/dev    # everything since a ref
 *   node scripts/feature-status.mjs --self-test          # parser/glob checks only
 */
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const REPORT = join(ROOT, 'docs', '12_feature_status.md')
const START = '<!-- feature-map:start -->'
const END = '<!-- feature-map:end -->'

function globToRegExp(glob) {
  let out = glob.replace(/[.+^${}()|[\]\\?]/g, '\\$&')
  out = out.replace(/\*\*\//g, '\u0000').replace(/\*\*/g, '.*').replace(/\*/g, '[^/]*').replace(/\u0000/g, '(?:.*/)?')
  return new RegExp(`^${out}$`)
}

function parseMap(text) {
  const start = text.indexOf(START)
  const end = text.indexOf(END)
  if (start < 0 || end < 0) throw new Error(`feature map markers missing from ${REPORT}`)
  return text
    .slice(start, end)
    .split('\n')
    .filter(line => line.startsWith('|'))
    .slice(2)
    .map(line => {
      const cells = line.split('|').map(cell => cell.trim())
      const paths = (cells[2] || '')
        .split(',')
        .map(path => path.trim().replace(/^`|`$/g, ''))
        .filter(Boolean)
      return { prefix: cells[1], paths }
    })
    .filter(entry => /^[A-Z]+$/.test(entry.prefix))
}

function git(args) {
  return execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
}

function changedFiles(base) {
  const tracked = git(['diff', '--name-only', '--no-renames', base || 'HEAD'])
  const untracked = git(['ls-files', '--others', '--exclude-standard'])
  return [...new Set(`${tracked}\n${untracked}`.split('\n').map(line => line.trim()).filter(Boolean))]
}

function selfTest() {
  const assertions = [
    [globToRegExp('backend/app/modules/quotations/**').test('backend/app/modules/quotations/service.py'), true],
    [globToRegExp('backend/app/modules/quotations/**').test('backend/app/modules/quotationsx/service.py'), false],
    [globToRegExp('frontend/app/pages/auth/**').test('frontend/app/pages/auth/login.vue'), true],
    [globToRegExp('frontend/app/pages/auth/**').test('frontend/app/pages/login.vue'), false],
    [globToRegExp('backend/app/core/**').test('backend/app/core/fx.py'), true],
    [globToRegExp('backend/app/core/*.py').test('backend/app/core/fx.py'), true],
    [globToRegExp('backend/app/core/*.py').test('backend/app/core/nested/fx.py'), false],
  ]
  for (const [actual, expected] of assertions) {
    if (actual !== expected) throw new Error(`self-test failed: expected ${expected}, got ${actual}`)
  }
  const sample = parseMap(
    `${START}\n| Prefix | Paths |\n|---|---|\n| QUOT | \`backend/app/modules/quotations/**\`, \`frontend/app/pages/quotations/**\` |\n${END}`,
  )
  if (sample.length !== 1 || sample[0].prefix !== 'QUOT' || sample[0].paths.length !== 2) {
    throw new Error('self-test failed: map parsing')
  }
  const report = parseMap(readFileSync(REPORT, 'utf8'))
  if (report.length < 10) throw new Error(`self-test failed: only ${report.length} map rows in the report`)
  console.log(`feature-status self-test passed (${report.length} mapped groups)`)
}

function main() {
  const args = process.argv.slice(2)
  if (args.includes('--self-test')) {
    selfTest()
    return
  }
  const baseIndex = args.indexOf('--base')
  const base = baseIndex >= 0 ? args[baseIndex + 1] : undefined
  const files = changedFiles(base)
  const map = parseMap(readFileSync(REPORT, 'utf8'))
  const hits = new Map()
  const unmapped = []

  for (const file of files) {
    const match = map.find(entry => entry.paths.some(glob => globToRegExp(glob).test(file)))
    if (match) {
      if (!hits.has(match.prefix)) hits.set(match.prefix, [])
      hits.get(match.prefix).push(file)
    } else {
      unmapped.push(file)
    }
  }

  console.log(`Changed files: ${files.length}${base ? ` (since ${base})` : ' (working tree vs HEAD)'}`)
  if (hits.size === 0) {
    console.log('No feature group matched. Documentation, comment and formatting edits need no status row.')
  }
  for (const [prefix, matched] of [...hits].sort()) {
    console.log(`\n${prefix}  (${matched.length} file${matched.length === 1 ? '' : 's'})`)
    for (const file of matched.slice(0, 6)) console.log(`  - ${file}`)
    if (matched.length > 6) console.log(`  ... and ${matched.length - 6} more`)
  }
  if (unmapped.length > 0) {
    console.log(`\nUnmapped (${unmapped.length}): decide whether any is PLAT or a new feature prefix`)
    for (const file of unmapped.slice(0, 10)) console.log(`  - ${file}`)
    if (unmapped.length > 10) console.log(`  ... and ${unmapped.length - 10} more`)
  }
  console.log('\nReview only these rows in docs/12_feature_status.md, run the focused test,')
  console.log('then record status/evidence/Last Verified. WORKING requires evidence you ran.')
}

try {
  main()
} catch (error) {
  console.error(`feature-status: ${error.message}`)
  process.exitCode = 2
}
