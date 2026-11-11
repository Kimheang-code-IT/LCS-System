import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const read = (path: string) => readFileSync(`${APP}/${path}`, 'utf8')

const charges = read('components/freight/JobCharges.vue')
const detail = read('components/freight/JobDetail.vue')
const saveGrid = read('components/table/AppSaveGrid.vue')

describe('service charge tab saves with the page header', () => {
  it('drops the grid save/cancel buttons and writes the pending change instead', () => {
    expect(charges).toContain('hide-save-actions')
    expect(charges).toContain('defineExpose({ savePending })')
    // One page save writes the grid's change set; nothing saves on its own.
    expect(saveGrid).toContain('pendingChange: changeSet')
    expect(saveGrid).toContain('props.hideSaveActions')
    expect(detail).toContain('chargesTab.value?.savePending()')
    // A refused charge save stops the page save (errors stay on the tab).
    expect(detail).toContain('if (chargesSaved === false) return')
    // The tab stays mounted after its first visit so unsaved rows survive a
    // tab switch; only the page header persists them.
    expect(detail).toContain('v-show="activeTab === \'charges\'"')
  })

  it('totals the unsaved working rows, not just the saved ones', () => {
    expect(charges).toContain('@update:draft="draftRows = $event"')
    expect(charges).toContain('const summaryRows = computed(() => draftRows.value.length ? draftRows.value : rows.value)')
    expect(charges).toContain('serviceChargeTotals(summaryRows.value')
    expect(charges).toContain('v-if="summaryRows.length"')
  })

  it('reports the grid dirty state to the page', () => {
    expect(charges).toContain('@update:dirty="emit(\'update:dirty\', $event)"')
    expect(detail).toContain('chargesDirty')
    expect(detail).toContain('const jobDirty = computed(() => chargesDirty.value')
  })
})
