export interface CsvField {
  label: string
  value: string
}

/** Escape and download any row list as a CSV file (client side). */
export function downloadCsv(options: {
  filename: string
  fields: CsvField[]
  rows: Array<Record<string, unknown>>
}) {
  const { filename, fields, rows } = options
  const csv = [
    fields.map(field => field.label),
    ...rows.map(row => fields.map(field => String(row[field.value] ?? ''))),
  ]
    .map(line => line.map(csvCell).join(','))
    .join('\n')
  downloadBlob(new Blob([csv], { type: 'text/csv' }), filename)
}

/**
 * One CSV cell: quoted/escaped, and neutralised when a spreadsheet would treat
 * it as a formula. A number (including a negative amount) stays data.
 */
export function csvCell(value: unknown) {
  const text = String(value ?? '')
  const numeric = /^-?\d+(?:\.\d+)?$/.test(text)
  const dangerous = text.startsWith('=') || text.startsWith('+') || text.startsWith('@')
    || text.startsWith('\t') || text.startsWith('\r')
    || (text.startsWith('-') && !numeric)
  return `"${(dangerous ? `'${text}` : text).replaceAll('"', '""')}"`
}

/** Save an already-built file (for example a report the backend streamed). */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  // Defer revocation: some browsers start the download asynchronously.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
