import { useLcsRepositories } from '~/repositories'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { hasSourcePermission } from '~/utils/freight/permissions'
import { rememberIdempotencyKey, clearIdempotencyKey } from '~/utils/freight/idempotency'
import type { SourcePermission } from '~/types/domain'

export function useLcs() {
  const repos = useLcsRepositories()
  const { t } = useI18n()
  const store = useFreightStore()
  const auth = useAuthStore()

  function can(code: SourcePermission) {
    return hasSourcePermission(auth.user, code)
  }

  /**
   * Turn a rejected command into a single safe sentence.
   *
   * Callers render it next to the form or the page: command failures are
   * business-rule or dependency refusals, which must never be reported as a
   * toast. Returns the message so it can be rendered inline.
   */
  function errorMessage(error: unknown) {
    return apiErrorMessage(error, t('api.somethingWentWrong'))
  }

  /** Kept for call sites that only need the failure handled, not shown. */
  function reportError(error: unknown) {
    return errorMessage(error)
  }

  async function runCommand<T>(command: string, entityId: string, fn: (key: string) => Promise<T>) {
    const key = rememberIdempotencyKey(command, entityId)
    const result = await fn(key)
    clearIdempotencyKey(command, entityId)
    store.reload()
    return result
  }

  return {
    ...repos,
    can,
    errorMessage,
    reportError,
    runCommand,
  }
}
