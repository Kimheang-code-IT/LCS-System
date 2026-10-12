import { localStore } from '~/utils/storage/local'

const AuthKeys = {
  REMEMBER_EMAIL: 'login:remember:email',
  REMEMBER_ENABLED: 'login:remember:enabled',
} as const

export type RememberMeState = {
  enabled: boolean
  email: string
}

export function readRememberMe(): RememberMeState {
  const raw = localStore.get<unknown>(AuthKeys.REMEMBER_ENABLED)
  const enabled = raw === true || raw === 1 || raw === '1'
  const email = enabled ? (localStore.get<string>(AuthKeys.REMEMBER_EMAIL) || '') : ''
  return { enabled, email }
}

/**
 * Persist (or clear) the Remember me preference. The email is kept only while
 * the option is enabled; authentication secrets are never stored here.
 */
export function writeRememberMe(state: RememberMeState): void {
  if (state.enabled && state.email) {
    localStore.set(AuthKeys.REMEMBER_ENABLED, true)
    localStore.set(AuthKeys.REMEMBER_EMAIL, state.email)
    return
  }
  localStore.remove(AuthKeys.REMEMBER_ENABLED)
  localStore.remove(AuthKeys.REMEMBER_EMAIL)
}
