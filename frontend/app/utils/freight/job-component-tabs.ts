import { resolveComponentInstanceMode } from '~/utils/freight/component-instance-mode'

/** Core service-order tabs are fixed Vue sections. Extra tabs come from Component Groups. */

export const JOB_FIXED_WORKSPACE_SECTIONS = ['overview', 'route', 'containers'] as const
export const JOB_TRAILING_WORKSPACE_SECTIONS = ['finance', 'files'] as const

export const JOB_CORE_WORKSPACE_SECTIONS = [
  ...JOB_FIXED_WORKSPACE_SECTIONS,
  ...JOB_TRAILING_WORKSPACE_SECTIONS,
] as const

/** Known group slugs for icons and deep-link aliases only — not fallback tabs. */
export const JOB_DEFAULT_COMPONENT_SECTIONS = [
  'invoice',
  'packing-list',
  'shipment-registration',
  'bill',
  'customs',
] as const

const RESERVED_TAB_IDS = new Set<string>(JOB_CORE_WORKSPACE_SECTIONS)

export type JobWorkspaceTabOptions = {
  direction?: string
  assignments?: Array<Record<string, unknown>>
}

function normalizeMatch(value: unknown) {
  return String(value || '').trim().toLowerCase().replace(/[\s_]+/g, '-')
}

export function isConfigFlagYes(value: unknown) {
  if (value === true || value === 1) return true
  if (value === false || value === 0 || value == null) return false
  const flag = String(value).trim().toLowerCase()
  if (['no', 'false', '0', 'n'].includes(flag)) return false
  return flag === 'yes' || flag === 'true' || flag === '1' || flag === 'y'
}

export function componentGroupTabId(group: Record<string, unknown>) {
  const code = String(group.code || '').trim()
  if (!code) return ''
  return code.toLowerCase().replace(/_/g, '-')
}

export function isReservedJobWorkspaceSection(id: string) {
  return RESERVED_TAB_IDS.has(id)
}

export function isFixedJobWorkspaceSection(id: string) {
  return isReservedJobWorkspaceSection(id)
}

export function isActiveComponentGroup(group: Record<string, unknown>) {
  const status = String(group.status || 'Active').trim().toUpperCase()
  return !status || status === 'ACTIVE'
}

export function isActiveAssignment(row: Record<string, unknown>) {
  const status = String(row.status || 'Active').trim().toUpperCase()
  return !status || status === 'ACTIVE'
}

/** Yes (default) shows the group as a service-order tab. */
export function isJobWorkspaceComponentGroup(group: Record<string, unknown>) {
  if (!isActiveComponentGroup(group)) return false
  return isConfigFlagYes(group.showOnJobWorkspace ?? 'Yes')
}

export function groupMatchesAssignment(group: Record<string, unknown>, assignment: Record<string, unknown>) {
  const assigned = normalizeMatch(assignment.componentGroup || assignment.groupCode || assignment.group)
  if (!assigned) return false
  return assigned === normalizeMatch(group.code) || assigned === normalizeMatch(group.name)
}

export function assignmentMatchesDirection(row: Record<string, unknown>, direction?: string) {
  const wanted = normalizeMatch(direction)
  if (!wanted) return true
  return normalizeMatch(row.tradeDirection) === wanted
}

function groupAllowedForDirection(
  group: Record<string, unknown>,
  assignments: Array<Record<string, unknown>>,
  direction?: string,
) {
  if (!direction || !assignments.length) return true
  const forGroup = assignments.filter(row => groupMatchesAssignment(group, row))
  if (!forGroup.length) return true
  return forGroup.some(row => assignmentMatchesDirection(row, direction))
}

export function jobComponentSectionsFromGroups(
  groups: Array<Record<string, unknown>>,
  options: JobWorkspaceTabOptions = {},
) {
  const assignments = (options.assignments || []).filter(isActiveAssignment)
  return [...groups]
    .filter(isJobWorkspaceComponentGroup)
    .filter((group) => {
      const id = componentGroupTabId(group)
      if (!id || isReservedJobWorkspaceSection(id)) return false
      return groupAllowedForDirection(group, assignments, options.direction)
    })
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))
    .map(componentGroupTabId)
    .filter(Boolean)
}

export function jobWorkspaceSectionList(
  groups?: Array<Record<string, unknown>>,
  options: JobWorkspaceTabOptions = {},
) {
  const documentTabs = groups?.length ? jobComponentSectionsFromGroups(groups, options) : []
  return [
    ...JOB_FIXED_WORKSPACE_SECTIONS,
    ...documentTabs,
    ...JOB_TRAILING_WORKSPACE_SECTIONS,
  ]
}

export function groupCodeForSection(section: string, groups: Array<Record<string, unknown>> = []) {
  const matched = groups.find(group => componentGroupTabId(group) === section)
  if (matched) return String(matched.code || '').trim().toUpperCase()
  return section.trim().toUpperCase().replace(/-/g, '_')
}

export function groupForSection(section: string, groups: Array<Record<string, unknown>> = []) {
  return groups.find(group => componentGroupTabId(group) === section)
    || groups.find(group => String(group.code || '').trim().toUpperCase() === groupCodeForSection(section, groups))
    || null
}

export function resolveGroupTemplate(params: {
  group: Record<string, unknown> | null
  templates: Array<Record<string, unknown>>
  assignments?: Array<Record<string, unknown>>
  direction?: string
}) {
  const { group } = params
  if (!group) return null
  const templates = params.templates.filter((row) => {
    const status = String(row.status || 'Active').trim().toUpperCase()
    return !status || status === 'ACTIVE'
  })
  const assignments = (params.assignments || [])
    .filter(isActiveAssignment)
    .filter(row => assignmentMatchesDirection(row, params.direction) && groupMatchesAssignment(group, row))
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))
  const named = String(assignments[0]?.componentTemplate || '').trim()
  const version = String(assignments[0]?.templateVersion || '').trim()

  const matchNamed = (row: Record<string, unknown>) =>
    normalizeMatch(row.name) === normalizeMatch(named) || normalizeMatch(row.code) === normalizeMatch(named)

  if (named) {
    const versioned = version
      ? templates.find(row => matchNamed(row) && String(row.version || '') === version)
      : null
    const match = versioned || templates.find(matchNamed)
    if (match) return match
  }

  return templates.find(row =>
    normalizeMatch(row.group) === normalizeMatch(group.code)
    || normalizeMatch(row.group) === normalizeMatch(group.name),
  ) || null
}

export function assignmentForGroup(params: {
  group: Record<string, unknown> | null
  assignments?: Array<Record<string, unknown>>
  direction?: string
}) {
  if (!params.group) return null
  return (params.assignments || [])
    .filter(isActiveAssignment)
    .filter(row => assignmentMatchesDirection(row, params.direction) && groupMatchesAssignment(params.group!, row))
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))[0] || null
}

export function isRepeatableComponent(assignment: Record<string, unknown> | null, template: Record<string, unknown> | null) {
  return resolveComponentInstanceMode(assignment, template) === 'REPEATABLE'
}

export function jobWorkspaceSectionIcon(id: string) {
  const icons: Record<string, string> = {
    overview: 'i-lucide-layout-dashboard',
    route: 'i-lucide-map-pinned',
    containers: 'i-lucide-container',
    invoice: 'i-lucide-file-text',
    'packing-list': 'i-lucide-list',
    'shipment-registration': 'i-lucide-clipboard-list',
    bill: 'i-lucide-receipt',
    customs: 'i-lucide-landmark',
    finance: 'i-lucide-banknote',
    files: 'i-lucide-paperclip',
  }
  return icons[id] || 'i-lucide-file-text'
}

export function firstJobDocumentSection(
  groups?: Array<Record<string, unknown>>,
  options: JobWorkspaceTabOptions = {},
) {
  return jobWorkspaceSectionList(groups, options).find(id => !isFixedJobWorkspaceSection(id)) || ''
}
