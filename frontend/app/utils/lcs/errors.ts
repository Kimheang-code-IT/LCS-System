import type { LcsApiErrorBody, LcsErrorCode } from '~/types/lcs/domain'

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

export function newRequestId() {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function domainError(
  code: LcsErrorCode,
  message: string,
  options: { statusCode?: number, field_errors?: Record<string, string> } = {},
) {
  return new LcsDomainError({
    code,
    message,
    request_id: newRequestId(),
    field_errors: options.field_errors,
  }, options.statusCode ?? (code === 'ACCESS_DENIED' || code === 'BRANCH_SCOPE_DENIED' ? 403 : 409))
}

export function isLcsDomainError(error: unknown): error is LcsDomainError {
  return error instanceof LcsDomainError
}
