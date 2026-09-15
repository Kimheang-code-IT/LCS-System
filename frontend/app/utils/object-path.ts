/**
 * Read a nested value from an object using a dotted path (`a.b.c`).
 */
export function getByPath(source: unknown, path: string): unknown {
  if (!source || typeof source !== 'object' || !path) return undefined
  const parts = path.split('.').filter(Boolean)
  let current: any = source
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined
    current = current[part]
  }
  return current
}

/**
 * Write a nested value on an object using a dotted path (`a.b.c`).
 * Mutates `target` in place and creates missing plain objects along the path.
 */
export function setByPath(target: Record<string, any>, path: string, value: unknown) {
  if (!target || !path) return
  const parts = path.split('.').filter(Boolean)
  if (!parts.length) return

  let current: Record<string, any> = target
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i]!
    if (current[part] == null || typeof current[part] !== 'object') {
      current[part] = {}
    }
    current = current[part]
  }
  current[parts[parts.length - 1]!] = value
}
