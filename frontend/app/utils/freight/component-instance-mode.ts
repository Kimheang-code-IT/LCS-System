import {
  COMPONENT_INSTANCE_MODES,
  COMPONENT_INSTANCE_MODE_OVERRIDES,
} from '~/config/freight-options'

export { COMPONENT_INSTANCE_MODES, COMPONENT_INSTANCE_MODE_OVERRIDES }

export type ComponentInstanceMode = typeof COMPONENT_INSTANCE_MODES[number]
export type ComponentInstanceModeOverride = typeof COMPONENT_INSTANCE_MODE_OVERRIDES[number]

function normalized(value: unknown) {
  return String(value ?? '').trim().toUpperCase().replace(/[\s-]+/g, '_')
}

export function legacyRepeatable(value: unknown) {
  if (value === true || value === 1) return true
  if (value === false || value === 0 || value == null) return false
  return ['YES', 'TRUE', '1', 'Y', 'REPEATABLE'].includes(normalized(value))
}

export function normalizeComponentInstanceMode(
  value: unknown,
  legacyValue?: unknown,
): ComponentInstanceMode {
  const mode = normalized(value)
  if (mode === 'REPEATABLE') return 'REPEATABLE'
  if (mode === 'SINGLE' || mode === 'SINGLE_INSTANCE') return 'SINGLE'
  return legacyRepeatable(legacyValue) ? 'REPEATABLE' : 'SINGLE'
}

export function normalizeComponentInstanceModeOverride(value: unknown): ComponentInstanceModeOverride {
  const mode = normalized(value)
  if (mode === 'REPEATABLE') return 'REPEATABLE'
  if (mode === 'SINGLE' || mode === 'SINGLE_INSTANCE') return 'SINGLE'
  return 'INHERIT'
}

/** Assignment override -> template default -> legacy flags -> SINGLE. */
export function resolveComponentInstanceMode(
  assignment: Record<string, unknown> | null | undefined,
  template: Record<string, unknown> | null | undefined,
): ComponentInstanceMode {
  const override = normalizeComponentInstanceModeOverride(
    assignment?.instanceModeOverride ?? assignment?.instanceMode,
  )
  if (override !== 'INHERIT') return override

  // Legacy assignment Yes meant an explicit repeatable assignment. Legacy No was
  // normally a copied template default, so it safely inherits during migration.
  if (legacyRepeatable(assignment?.repeatable)) return 'REPEATABLE'
  return normalizeComponentInstanceMode(template?.instanceMode, template?.repeatable)
}

export function componentInstanceLimits(
  assignment: Record<string, unknown> | null | undefined,
  template: Record<string, unknown> | null | undefined,
) {
  const required = legacyRepeatable(assignment?.required ?? template?.required)
  const rawMinimum = assignment?.minimumInstances ?? template?.minimumInstances
  const rawMaximum = assignment?.maximumInstances ?? template?.maximumInstances
  const parsedMinimum = Number(rawMinimum)
  const parsedMaximum = Number(rawMaximum)
  const minimum = Number.isFinite(parsedMinimum) && parsedMinimum >= 0
    ? Math.floor(parsedMinimum)
    : (required ? 1 : 0)
  const maximum = Number.isFinite(parsedMaximum) && parsedMaximum > 0
    ? Math.max(minimum, Math.floor(parsedMaximum))
    : undefined
  return { minimum, maximum }
}

export function normalizeComponentTemplateRecord<T extends Record<string, unknown>>(row: T): T {
  const instanceMode = normalizeComponentInstanceMode(row.instanceMode, row.repeatable)
  return { ...row, instanceMode, repeatable: instanceMode === 'REPEATABLE' ? 'Yes' : 'No' }
}

export function normalizeComponentAssignmentRecord<T extends Record<string, unknown>>(row: T): T {
  const explicit = row.instanceModeOverride ?? row.instanceMode
  const instanceModeOverride = explicit == null || String(explicit).trim() === ''
    ? (legacyRepeatable(row.repeatable) ? 'REPEATABLE' : 'INHERIT')
    : normalizeComponentInstanceModeOverride(explicit)
  return { ...row, instanceModeOverride }
}

export function componentSummaryAttributes(template: Record<string, unknown> | null | undefined) {
  const attributes = (Array.isArray(template?.attributes) ? template.attributes : []) as Array<Record<string, unknown>>
  const active = attributes
    .filter(row => !row.status || normalized(row.status) === 'ACTIVE')
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))
  const selected = active.filter(row => legacyRepeatable(row.showInSummary))
  return (selected.length ? selected : active).slice(0, 4)
}
