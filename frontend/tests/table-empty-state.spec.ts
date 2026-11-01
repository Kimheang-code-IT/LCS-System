import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = (file: string) =>
  readFileSync(fileURLToPath(new URL(`../app/${file}`, import.meta.url)), 'utf8')

describe('empty table behavior', () => {
  /**
   * The shared table keeps its whole structure mounted with zero rows: UTable
   * always renders, and the empty state lives in one body row that spans all
   * visible columns (UTable's #empty slot supplies the colspan itself).
   */
  const listTable = source('components/table/AppListTable.vue')

  it('never unmounts the table when there are no rows', () => {
    expect(listTable).not.toMatch(/<UTable[^>]*v-if/)
    expect(listTable).not.toContain('<UEmpty')
    expect(listTable).toMatch(/<template #empty>/)
    // The toolbar (search/sort/filters) and the pagination footer are outside
    // the row area and stay rendered — only the body differs.
    expect(listTable).toMatch(/UPagination[\s\S]*:total="total"/)
  })

  it('distinguishes an empty database from an empty filtered result', () => {
    expect(listTable).toMatch(/hasSearchTerm/)
    expect(listTable).toMatch(/noMatchingRecords/)
    expect(listTable).toMatch(/noRecords/)
  })

  it('does not duplicate header create actions inside the empty state', () => {
    for (const file of [
      'components/freight/WorkspaceView.vue',
      'components/freight/ReportsView.vue',
      'pages/configuration/versions/index.vue',
    ]) {
      expect(source(file), file).not.toContain(':empty-actions=')
    }
    // The shared component no longer carries the deprecated prop either.
    expect(listTable).not.toContain('emptyActions')
  })

  it('renders the loading state inside the table body', () => {
    expect(listTable).toMatch(/<template #loading>/)
    expect(listTable).toContain("t('common.loading')")
  })

  it('related-record tables keep their headers with zero rows', () => {
    const related = source('components/table/AppRelatedRecords.vue')
    expect(related).not.toMatch(/<UTable[^>]*v-if/)
    expect(related).toMatch(/<template #empty>/)
  })
})