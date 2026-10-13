import type { LcsApiErrorBody } from '~/types/domain'

export class LcsDomainError extends Error {
  readonly code: string
  readonly request_id: string
  readonly field_errors?: Record<string, string>
  readonly statusCode: number

  constructor(body: LcsApiErrorBody, statusCode = 409) {
    super(body.message)
    this.name = 'LcsDomainError'
    this.code = body.code
    this.request_id = body.request_id
    this.field_errors = body.field_errors
    this.statusCode = statusCode
  }

  toBody(): LcsApiErrorBody {
    return {
      code: this.code,
      message: this.message,
      request_id: this.request_id,
      field_errors: this.field_errors,
    }
  }
}

export function isLcsDomainError(error: unknown): error is LcsDomainError {
  return error instanceof LcsDomainError
}

export type ApiErrorDetails = {
  message?: string
  fieldErrors?: Record<string, string>
  status?: number
}

/**
 * Read the API error envelope (`code`/`message`/`field_errors`) from either a
 * domain error or the raw fetch error thrown by `useApi`, so a form can place
 * the message inline instead of showing a toast.
 */
export function apiErrorDetails(error: unknown): ApiErrorDetails {
  if (isLcsDomainError(error)) {
    return { message: error.message, fieldErrors: error.field_errors, status: error.statusCode }
  }
  const raw = error as {
    status?: number
    statusCode?: number
    data?: { message?: string, field_errors?: Record<string, string> }
  } | null
  const body = raw?.data
  return {
    message: typeof body?.message === 'string' ? body.message : undefined,
    fieldErrors: body?.field_errors,
    status: raw?.status ?? raw?.statusCode,
  }
}
