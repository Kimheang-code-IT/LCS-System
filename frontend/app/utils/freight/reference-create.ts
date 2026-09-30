import { freightModules } from '~/config/freight-modules'
import { referenceOptionSource } from '~/utils/freight/reference-options'

export type ReferenceCreateTarget = {
  /** Master Data module path, e.g. `/master-data/container-types`. */
  path: string
  /** Field stored as the select value on the created record. */
  valueField: string
}

/**
 * Resolve the Master Data create page for a reference-backed select field.
 * Returns null for static selects, missing modules or non-creatable modules.
 */
export function referenceCreateTarget(key: string): ReferenceCreateTarget | null {
  const source = referenceOptionSource(key)
  if (!source) return null
  const module = freightModules.find(item =>
    item.collection === source.collection
    && item.group === 'master'
    && item.canCreate !== false,
  )
  if (!module) return null
  return {
    path: `${module.path.replace(/\/$/, '')}/new`,
    valueField: source.valueField || 'code',
  }
}
