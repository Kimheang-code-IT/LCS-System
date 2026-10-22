import type {
  ComponentTabAttribute,
  ComponentTabGroup,
  ComponentTabRuntime,
  ConfigurationVersion,
} from '~/types/component-config'

/** Stored snapshot shape; deliberately narrower than the live ORM payload. */
export interface SnapshotAttribute {
  id?: string
  code?: string | null
  label?: string | null
  labelKm?: string | null
  dataType?: string | null
  inputType?: string | null
  referenceType?: string | null
  isRequired?: boolean
  isVisible?: boolean
  defaultValue?: string | null
  placeholder?: string | null
  width?: string | null
  options?: ComponentTabAttribute['options']
  validationRules?: Record<string, unknown>
  displayOrder?: number
}

export interface SnapshotGroup {
  id?: string
  tabGroupId?: string | null
  code?: string | null
  name?: string | null
  nameKm?: string | null
  renderMode?: string | null
  displayOrder?: number
  displayMode?: string | null
  dataCardinality?: string | null
  formColumns?: number | null
  showGroupTitle?: boolean
  editable?: boolean
  collapsible?: boolean
  defaultExpanded?: boolean
  attributes?: SnapshotAttribute[]
}

export interface SnapshotTab {
  id?: string
  code?: string | null
  name?: string | null
  tradeDirectionId?: string | null
  displayOrder?: number
  groups?: SnapshotGroup[]
}

/**
 * Convert a stored snapshot into the runtime tab shape the read-only preview
 * renders. Historical snapshots keep the persisted field names (`dataType`,
 * `displayOrder`); the live renderer speaks `fieldType`, `sortOrder`.
 */
export function snapshotPreviewTabs(version: ConfigurationVersion | null): ComponentTabRuntime[] {
  const snapshot = version?.configSnapshot as { tabs?: SnapshotTab[] } | null | undefined
  return (snapshot?.tabs || []).map((tab, tabIndex) => ({
    id: String(tab.id || tab.code || tabIndex),
    code: String(tab.code || ''),
    name: String(tab.name || tab.code || ''),
    tradeDirectionId: tab.tradeDirectionId || null,
    displayOrder: Number(tab.displayOrder ?? tabIndex),
    groups: (tab.groups || []).map((group, groupIndex) => snapshotGroup(group, groupIndex)),
  }))
}

function snapshotGroup(group: SnapshotGroup, groupIndex: number): ComponentTabGroup {
  const legacyForm = (group.renderMode || 'table') === 'form'
  return {
    id: String(group.id || group.code || groupIndex),
    tabGroupId: group.tabGroupId || undefined,
    code: String(group.code || ''),
    name: String(group.name || group.code || ''),
    nameKm: group.nameKm || null,
    renderMode: (group.renderMode === 'form' ? 'form' : 'table'),
    displayOrder: Number(group.displayOrder ?? groupIndex),
    displayMode: (group.displayMode || (legacyForm ? 'form_only' : 'table_only')) as ComponentTabGroup['displayMode'],
    dataCardinality: (group.dataCardinality || (legacyForm ? 'single' : 'multiple')) as ComponentTabGroup['dataCardinality'],
    formColumns: Number(group.formColumns ?? 3) as ComponentTabGroup['formColumns'],
    showGroupTitle: group.showGroupTitle !== false,
    editable: group.editable !== false,
    collapsible: Boolean(group.collapsible),
    defaultExpanded: group.defaultExpanded !== false,
    attributes: (group.attributes || []).map((attribute, attributeIndex) => snapshotAttribute(attribute, attributeIndex)),
    rows: [],
  }
}

function snapshotAttribute(attribute: SnapshotAttribute, index: number): ComponentTabAttribute {
  return {
    id: String(attribute.id || attribute.code || index),
    code: String(attribute.code || ''),
    label: String(attribute.label || attribute.code || ''),
    labelKm: attribute.labelKm || null,
    fieldType: (attribute.dataType || 'text') as ComponentTabAttribute['fieldType'],
    inputType: attribute.inputType || null,
    referenceType: attribute.referenceType as ComponentTabAttribute['referenceType'] || null,
    isRequired: Boolean(attribute.isRequired),
    isVisible: attribute.isVisible !== false,
    defaultValue: attribute.defaultValue || null,
    placeholder: attribute.placeholder || null,
    width: attribute.width || null,
    options: attribute.options || [],
    validationRules: attribute.validationRules || {},
    sortOrder: Number(attribute.displayOrder ?? index),
  }
}
