/**
 * Error classification for the HTTP layer.
 *
 * ofetch throws a `FetchError` for an HTTP error response *and* for a network
 * failure. Only the latter has no status, so the status — not the error name —
 * decides whether the UI may say "could not reach the server".
 */

export type ApiFailure = {
  name?: string
  status?: number
  statusCode?: number
  cause?: { name?: string }
}

/** True only when no HTTP response arrived (DNS, offline, timeout, reset). */
export function isNetworkFailure(error: ApiFailure | undefined | null): boolean {
  if (!error || error.name !== 'FetchError') return false
  return !Number(error.status ?? error.statusCode ?? 0)
}
