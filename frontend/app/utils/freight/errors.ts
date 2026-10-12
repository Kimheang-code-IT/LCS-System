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
