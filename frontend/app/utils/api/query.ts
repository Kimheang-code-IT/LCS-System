export function compactQuery<T extends object>(query: T | undefined): Partial<T> | undefined {
  if (!query) return undefined

  const compacted = Object.fromEntries(
    Object.entries(query).filter(([, value]) => {
      if (value === null || value === undefined) return false
      if (typeof value === 'string') return value.trim().length > 0
      if (Array.isArray(value)) return value.length > 0
      return true
    })
  ) as Partial<T>

  return Object.keys(compacted).length ? compacted : undefined
}

export function stableQueryString(query: object | undefined) {
  const compacted = compactQuery(query)
  if (!compacted) return ''
  const entries = compacted as Record<string, unknown>
  return Object.keys(entries)
    .sort()
    .map(key => `${key}=${encodeURIComponent(String(entries[key]))}`)
    .join('&')
}
