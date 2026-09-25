/**
 * File-text extraction for indexing. Only real, supplied plain text is
 * returned; files without extractable content yield an empty string.
 */

export type ExtractInput = {
  fileName: string
  mimeType?: string
  /** Optional known plain-text body (txt/csv uploads). */
  rawText?: string
  /** Entity title / context for the extract. */
  contextTitle?: string
}

/**
 * Returns searchable plain text for an uploaded/linked file, or an empty
 * string when no real extractable text is available.
 */
export function extractText(input: ExtractInput): string {
  const name = String(input.fileName || 'file').trim()

  if (input.rawText && input.rawText.trim()) {
    return `${name}\n${input.rawText.trim()}`
  }

  return ''
}

/** Build a short snippet around the first query match. */
export function makeSnippet(text: string, query: string, radius = 72): string {
  const body = text.replace(/\s+/g, ' ').trim()
  if (!body) return ''
  const q = query.trim().toLowerCase()
  if (!q) return body.slice(0, radius * 2) + (body.length > radius * 2 ? '…' : '')

  const lower = body.toLowerCase()
  const idx = lower.indexOf(q)
  if (idx < 0) return body.slice(0, radius * 2) + (body.length > radius * 2 ? '…' : '')

  const start = Math.max(0, idx - radius)
  const end = Math.min(body.length, idx + q.length + radius)
  const prefix = start > 0 ? '…' : ''
  const suffix = end < body.length ? '…' : ''
  return `${prefix}${body.slice(start, end)}${suffix}`
}
