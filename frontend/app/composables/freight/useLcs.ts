import { useLcsRepositories } from '~/repositories'
import { isLcsDomainError } from '~/utils/freight/errors'
import { hasSourcePermission } from '~/utils/freight/permissions'
import { rememberIdempotencyKey, clearIdempotencyKey } from '~/utils/freight/idempotency'
import type { SourcePermission } from '~/types/domain'

export function useLcs() {
  const repos = useLcsRepositories()
  const toast = useToast()
  const { t } = useI18n()
  const store = useFreightStore()
  const auth = useAuthStore()

  function can(code: SourcePermission) {
    return hasSourcePermission(auth.user, code)
  }

  function reportError(error: unknown) {
    if (isLcsDomainError(error)) {
      toast.add({ title: error.message, color: 'error' })
      return error
    }
    toast.add({ title: t('api.somethingWentWrong'), color: 'error' })
    return error
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
    reportError,
    runCommand,
  }
}
