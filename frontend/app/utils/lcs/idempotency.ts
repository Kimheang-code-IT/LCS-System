export function createIdempotencyKey() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `idem_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

export function rememberIdempotencyKey(command: string, entityId: string) {
  const key = `lcs-idem:${command}:${entityId}`
  if (!import.meta.client) return createIdempotencyKey()
  const existing = sessionStorage.getItem(key)
  if (existing) return existing
  const next = createIdempotencyKey()
  sessionStorage.setItem(key, next)
  return next
}

export function clearIdempotencyKey(command: string, entityId: string) {
  if (!import.meta.client) return
  sessionStorage.removeItem(`lcs-idem:${command}:${entityId}`)
}
