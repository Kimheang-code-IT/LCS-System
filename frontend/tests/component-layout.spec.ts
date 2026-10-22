import { describe, expect, it } from 'vitest'
import {
  componentFormGridClass,
  componentGroupHasForm,
  componentGroupHasTable,
  componentGroupIsSingleRecord,
  componentInputType,
  legacyComponentLayout,
  resolveComponentLayout,
  visibleComponentAttributes,
} from '../app/utils/freight/component-layout'
import { componentGroupToFreightTable } from '../app/utils/freight/component-tabs'
import type { ComponentTabAttribute, ComponentTabGroup } from '../app/types/component-config'

function attribute(overrides: Partial<ComponentTabAttribute>): ComponentTabAttribute {
  return {
    id: '1',
    code: 'container_no',
    label: 'Container No.',
    fieldType: 'text',
    isRequired: false,
    sortOrder: 10,
    ...overrides,
  }
}

function group(overrides: Partial<ComponentTabGroup> = {}): ComponentTabGroup {
  return {
    id: '5',
    code: 'containers',
    name: 'Container Details',
    renderMode: 'table',
    displayOrder: 10,
    displayMode: 'table_only',
    dataCardinality: 'multiple',
    formColumns: 2,
    showGroupTitle: true,
    editable: true,
    collapsible: false,
    defaultExpanded: true,
    attributes: [],
    rows: [],
    ...overrides,
  }
}

describe('component layout', () => {
  it('falls back to the legacy render mode when a snapshot has no layout keys', () => {
    expect(legacyComponentLayout('form')).toMatchObject({
      displayMode: 'form_only',
      dataCardinality: 'single',
    })
    expect(legacyComponentLayout('table')).toMatchObject({
      displayMode: 'table_only',
      dataCardinality: 'multiple',
    })

    const snapshot = {
      id: '1',
      tabGroupId: '2',
      code: 'g',
      name: 'G',
      renderMode: 'form' as const,
      displayOrder: 10,
      attributes: [],
      rows: [],
    }
    expect(resolveComponentLayout(snapshot)).toMatchObject({
      displayMode: 'form_only',
      dataCardinality: 'single',
      formColumns: 3,
      editable: true,
    })
  })

  it('keeps per-assignment layout values independent', () => {
    const form = group({ displayMode: 'form_only', dataCardinality: 'single', formColumns: 1 })
    const table = group({ id: '6', displayMode: 'table_only', dataCardinality: 'multiple' })
    const mixed = group({ id: '7', displayMode: 'form_and_table', dataCardinality: 'multiple' })

    expect(componentGroupHasForm(form)).toBe(true)
    expect(componentGroupHasTable(form)).toBe(false)
    expect(componentGroupHasForm(table)).toBe(false)
    expect(componentGroupHasTable(table)).toBe(true)
    expect(componentGroupHasForm(mixed)).toBe(true)
    expect(componentGroupHasTable(mixed)).toBe(true)
    expect(componentGroupIsSingleRecord(form)).toBe(true)
    expect(componentGroupIsSingleRecord(table)).toBe(false)
  })

  it('maps the column count to a static grid class', () => {
    expect(componentFormGridClass(1)).toBe('grid grid-cols-1')
    expect(componentFormGridClass(2)).toContain('sm:grid-cols-2')
    expect(componentFormGridClass(3)).toContain('lg:grid-cols-3')
    expect(componentFormGridClass(4)).toContain('lg:grid-cols-4')
    expect(componentFormGridClass(9)).toContain('sm:grid-cols-2')
  })

  it('orders visible attributes and keeps hidden ones out of the table', () => {
    const hidden = attribute({ id: '2', code: 'seal_no', sortOrder: 20, isVisible: false })
    const second = attribute({ id: '3', code: 'container_type', sortOrder: 5 })
    const first = attribute({ id: '1', code: 'container_no', sortOrder: 1 })
    const componentGroup = group({ attributes: [second, hidden, first] })

    expect(visibleComponentAttributes(componentGroup).map(item => item.code)).toEqual([
      'container_no',
      'container_type',
    ])

    const table = componentGroupToFreightTable(componentGroup, {}, { hideTitle: true, hideAddRow: true })
    expect(table?.columns.map(column => column.key)).toEqual(['container_no', 'container_type'])
    expect(table?.hideTitle).toBe(true)
    expect(table?.hideAddRow).toBe(true)
  })

  it('honours a configured text input type and keeps date types intact', () => {
    expect(componentInputType({ fieldType: 'text', inputType: 'email' })).toBe('email')
    expect(componentInputType({ fieldType: 'text', inputType: 'bogus' })).toBe('text')
    expect(componentInputType({ fieldType: 'date', inputType: 'email' })).toBe('date')
    expect(componentInputType({ fieldType: 'datetime', inputType: null })).toBe('datetime-local')
  })
})
