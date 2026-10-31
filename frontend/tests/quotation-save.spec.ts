import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(__dirname, '../app/components/freight/DocumentView.vue'), 'utf8')

/**
 * Regression: the 2026-10-27 canSave refactor wired the inline-grid guard into
 * save() itself, so the header Save on /quotations/new silently did nothing —
 * for every role, not just narrow ones. The document save() gate and the
 * inline-grid gate are separate concerns and this pins that separation.
 */
describe('quotation save wiring', () => {
  it('save() is gated by canRunSave, which does not exclude quotations', () => {
    expect(source).toContain('if (!canRunSave.value) return')
    const runGuard = source.slice(source.indexOf('const canRunSave'), source.indexOf('const canSave'))
    expect(runGuard).toContain('validatePasswordStrength')
  })

  it('the inline save grid stays disabled for quotations', () => {
    expect(source).toContain('const canSave = computed(() => canRunSave.value && module.value?.collection !== \'quotations\')')
    expect(source).toContain(':can-save="canSave"')
  })
})