/**
 * Layout rules for the database-driven component groups.
 *
 * Layout belongs to the group's assignment on a tab (`ComponentTabGroup`), not
 * to the reusable group itself, so one tab can render a form, a table and a
 * form-plus-table side by side. Snapshots written before per-tab layouts
 * existed have no layout keys; they fall back to the legacy `renderMode` so a
 * historical Service Order still renders exactly as it was captured.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

import type {
  ComponentDataCardinality,
  ComponentDisplayMode,
  ComponentFormColumns,
  ComponentGroupLayout,
  ComponentRenderMode,
  ComponentTabAttribute,
  ComponentTabGroup,
} from '~/types/component-config'

export const COMPONENT_DISPLAY_MODE_VALUES: ComponentDisplayMode[] = [
  'form_only',
  'table_only',
  'form_and_table',
]

export const COMPONENT_DATA_CARDINALITY_VALUES: ComponentDataCardinality[] = ['single', 'multiple']
export const COMPONENT_FORM_COLUMN_VALUES: ComponentFormColumns[] = [1, 2, 3, 4]

type LayoutSource = Partial<ComponentGroupLayout> & {
  renderMode?: ComponentRenderMode | null
}

export function legacyComponentLayout(renderMode?: ComponentRenderMode | null): ComponentGroupLayout {
  return String(renderMode || '').trim().toLowerCase() === 'form'
    ? {
        displayMode: 'form_only',
        dataCardinality: 'single',
        formColumns: 3,
        showGroupTitle: true,
        editable: true,
        collapsible: false,
        defaultExpanded: true,
      }
    : {
        displayMode: 'table_only',
        dataCardinality: 'multiple',
        formColumns: 3,
        showGroupTitle: true,
        editable: true,
        collapsible: false,
        defaultExpanded: true,
      }
}

/** Resolve a group's effective layout, tolerating pre-layout snapshots. */
export function resolveComponentLayout(group: LayoutSource): ComponentGroupLayout {
  const fallback = legacyComponentLayout(group.renderMode)
  const columns = Number(group.formColumns)
  return {
    displayMode: group.displayMode && COMPONENT_DISPLAY_MODE_VALUES.includes(group.displayMode)
      ? group.displayMode
      : fallback.displayMode,
    dataCardinality: group.dataCardinality && COMPONENT_DATA_CARDINALITY_VALUES.includes(group.dataCardinality)
      ? group.dataCardinality
      : fallback.dataCardinality,
    formColumns: COMPONENT_FORM_COLUMN_VALUES.includes(columns as ComponentFormColumns)
      ? columns as ComponentFormColumns
      : fallback.formColumns,
    showGroupTitle: group.showGroupTitle ?? fallback.showGroupTitle,
    editable: group.editable ?? fallback.editable,
    collapsible: group.collapsible ?? fallback.collapsible,
    defaultExpanded: group.defaultExpanded ?? fallback.defaultExpanded,
  }
}

/** Tailwind grid class for a configured column count (all classes are static). */
export function componentFormGridClass(columns: number | null | undefined): string {
  switch (Number(columns)) {
    case 1:
      return 'grid grid-cols-1'
    case 4:
      return 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4'
    case 3:
      return 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3'
    case 2:
    default:
      return 'grid grid-cols-1 gap-4 sm:grid-cols-2'
  }
}

/** Should this group show a records table? */
export function componentGroupHasTable(group: LayoutSource): boolean {
  const mode = resolveComponentLayout(group).displayMode
  return mode === 'table_only' || mode === 'form_and_table'
}

/** Should this group show an input form? */
export function componentGroupHasForm(group: LayoutSource): boolean {
  const mode = resolveComponentLayout(group).displayMode
  return mode === 'form_only' || mode === 'form_and_table'
}

export function componentGroupIsSingleRecord(group: LayoutSource): boolean {
  const layout = resolveComponentLayout(group)
  return layout.dataCardinality === 'single' || layout.displayMode === 'form_only'
}

/** Attributes that render, in configured order. Hidden columns keep their values. */
export function visibleComponentAttributes(group: Pick<ComponentTabGroup, 'attributes'>): ComponentTabAttribute[] {
  return [...group.attributes]
    .filter(attribute => attribute.isVisible !== false)
    .sort((a, b) => a.sortOrder - b.sortOrder)
}

/** HTML input type for a free-text attribute, honouring the configured input type. */
export function componentInputType(attribute: Pick<ComponentTabAttribute, 'fieldType' | 'inputType'>): string {
  if (attribute.fieldType === 'date') return 'date'
  if (attribute.fieldType === 'datetime') return 'datetime-local'
  const allowed = new Set(['text', 'email', 'tel', 'url', 'search', 'password'])
  const configured = String(attribute.inputType || '').trim().toLowerCase()
  return allowed.has(configured) ? configured : 'text'
}
