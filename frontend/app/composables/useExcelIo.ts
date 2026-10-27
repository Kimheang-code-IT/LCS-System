import { useAuthStore } from '~/stores/auth'
import { csrfRequestHeaders } from '~/utils/security/csrf'
import { sameOriginApiUrl } from '~/utils/security/url'

export type ExcelColumn = {
  key: string
  kind: 'text' | 'number' | 'integer' | 'date' | 'boolean' | 'enum' | 'reference'
  required: boolean
  enum: string[]
  updatable: boolean
}

export type ExcelModuleInfo = {
  key: string
  name: string
  importEnabled: boolean
  exportEnabled: boolean
  templateVersion: number
  matchKey: string[]
  viewPermission: string
  managePermission: string
  createdBySupported?: boolean
  updatedBySupported?: boolean
  columns: ExcelColumn[]
}

export type ExcelPreviewRow = {
  excelRow: number
  identifier: string
  action: 'CREATE' | 'UPDATE' | 'SKIP' | 'ERROR'
  status: 'VALID' | 'INVALID'
  errors: string[]
}

export type ExcelImportSummary = {
  total: number
  create: number
  update: number
  skip: number
  error: number
}

export type ExcelImportJob = {
  id: string
  module: string
  fileName: string
  mode: string
  status: string
  totalRows: number
  created: number
  updated: number
  skipped: number
  failed: number
  errorSummary: string | null
  startedByUserId: string | null
  startedAt: string | null
  completedAt: string | null
}

export type ExcelValidateResult = {
  token: string
  module: string
  mode: string
  expiresAt: string
  summary: ExcelImportSummary
  rows: ExcelPreviewRow[]
}

export type ImportMode = 'CREATE_ONLY' | 'CREATE_AND_UPDATE' | 'VALIDATE_ONLY'

/** One shared client for the Excel Import & Export endpoints. */
export function useExcelIo() {
  const auth = useAuthStore()
  const config = useRuntimeConfig()
  const baseURL = String(config.public.apiBase || '') || (import.meta.client ? window.location.origin : '')

  async function rawFetch(path: string, init: RequestInit): Promise<Response> {
    const resolved = sameOriginApiUrl(path, baseURL)
    if (!resolved) throw new Error('API requests must use the configured API origin')
    return fetch(resolved, {
      credentials: 'include',
      ...init,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        ...(auth.accessToken ? { Authorization: `Bearer ${auth.accessToken}` } : {}),
        ...csrfRequestHeaders(init.method || 'GET', String(config.public.csrfCookieName), String(config.public.csrfHeaderName)),
        ...init.headers,
      },
    })
  }

  async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await rawFetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
    const body = await response.json()
    if (!response.ok) throw Object.assign(new Error(body.message || 'Request failed'), { statusCode: response.status, data: body })
    return (body.data ?? body) as T
  }

  /** Fetch a generated workbook and hand it to the browser as a download. */
  async function downloadFile(path: string, init: RequestInit = {}) {
    const response = await rawFetch(path, init)
    if (!response.ok) {
      let message = 'Download failed'
      try {
        const body = await response.json()
        message = body.message || message
      }
      catch { /* non-JSON error body */ }
      throw Object.assign(new Error(message), { statusCode: response.status })
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const match = /filename="([^"]+)"/.exec(disposition)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = match?.[1] || 'download.xlsx'
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    // Revoking synchronously cancels the download in some browsers.
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return {
    modules: () => json<ExcelModuleInfo[]>('/api/v1/excel/modules'),
    template: (module: string) => downloadFile(`/api/v1/excel/${module}/template`),
    validate: async (module: string, file: File, mode: ImportMode) => {
      const form = new FormData()
      form.append('file', file)
      form.append('mode', mode)
      const response = await rawFetch(`/api/v1/excel/${module}/validate`, { method: 'POST', body: form })
      const body = await response.json()
      if (!response.ok) throw Object.assign(new Error(body.message || 'Validation failed'), { statusCode: response.status, data: body })
      return body.data as ExcelValidateResult
    },
    preview: (token: string) => json<ExcelValidateResult>(`/api/v1/excel/imports/${token}`),
    commit: (token: string) => json<{ jobId: string, status: string } & ExcelImportSummary>(`/api/v1/excel/imports/${token}/commit`, { method: 'POST' }),
    cancel: (token: string) => json<{ status: string }>(`/api/v1/excel/imports/${token}/cancel`, { method: 'POST' }),
    errorReport: (token: string) => downloadFile(`/api/v1/excel/imports/${token}/error-report`),
    exportRows: async (module: string, ids: string[], options?: { format?: 'xlsx' | 'csv', filters?: Record<string, string> }) => downloadFile(`/api/v1/excel/${module}/export`, {
      method: 'POST',
      // Without this the browser labels the JSON string body text/plain and FastAPI rejects it.
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(ids.length ? { ids } : {}),
        ...(options?.format ? { format: options.format } : {}),
        ...(options?.filters ? { filters: options.filters } : {}),
      }),
    }),
    exportCount: (module: string, filters: Record<string, string>) => {
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value))
      const suffix = query.toString() ? `?${query.toString()}` : ''
      return json<{ count: number }>(`/api/v1/excel/${module}/export-count${suffix}`)
    },
    history: (module?: string) => json<{ items: ExcelImportJob[] }>(
      `/api/v1/excel/history${module ? `?module=${encodeURIComponent(module)}` : ''}`,
    ),
  }
}
