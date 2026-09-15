/** Default invoice logo used when tenant branding has no printable logo. */
export const DEFAULT_INVOICE_LOGO_URL = '/lcs-invoice-logo.png'

/**
 * Accept only an application-local route. This prevents print-preview return
 * links from becoming external redirects or malformed Windows-style paths.
 */
export function safePrintReturnPath(value: unknown, fallback = '/'): string {
  const raw = Array.isArray(value) ? value[0] : value
  const path = String(raw || '').trim()
  if (!path.startsWith('/') || path.startsWith('//')) return fallback
  if (path.includes('\\') || [...path].some(char => char.charCodeAt(0) < 32)) return fallback
  return path
}

export function documentDetailPath(modulePath: string, recordId: string): string {
  const base = safePrintReturnPath(modulePath, '/')
  const id = encodeURIComponent(String(recordId || '').trim())
  return id ? `${base.replace(/\/$/, '')}/${id}` : base
}

export const PRINT_AUTO_QUERY = 'autoPrint'

export function isAutoPrintRoute(query: Record<string, unknown>): boolean {
  const raw = query[PRINT_AUTO_QUERY] ?? query.autoPrint
  const value = Array.isArray(raw) ? raw[0] : raw
  const normalized = String(value || '').trim().toLowerCase()
  return normalized === '1' || normalized === 'true'
}

export function buildPrintRoute(options: {
  collection: string
  recordId: string
  template: string
  returnTo?: unknown
  modulePath?: string
  container?: number
  lineIndex?: number
  autoPrint?: boolean
}) {
  const fallback = documentDetailPath(options.modulePath || `/${options.collection}`, options.recordId)
  const query: Record<string, string> = {
    template: options.template,
    returnTo: safePrintReturnPath(options.returnTo, fallback),
  }
  if (options.autoPrint !== false) query[PRINT_AUTO_QUERY] = '1'
  if (options.container !== undefined) query.container = String(options.container)
  if (options.lineIndex !== undefined) query.line = String(options.lineIndex)
  return {
    path: `/print/${options.collection}/${encodeURIComponent(String(options.recordId || '').trim())}`,
    query,
  }
}
