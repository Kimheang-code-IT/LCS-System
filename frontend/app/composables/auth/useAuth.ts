import type { AuthUser } from '~/types/auth-user'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'

type LoginResult = { user: AuthUser }

/**
 * Auth composable. Uses the real `/api/v1/auth` API.
 */
export function useAuth() {
  const api = useApi()
  const auth = useAuthStore()

  function payloadOf(response: unknown): Record<string, unknown> {
    if (response && typeof response === 'object' && 'data' in response) {
      const data = (response as { data?: unknown }).data
      if (data && typeof data === 'object') return data as Record<string, unknown>
    }
    return (response && typeof response === 'object' ? response : {}) as Record<string, unknown>
  }

  async function loginWithCredentials(email: string, password: string): Promise<{ data: LoginResult }> {
    const response = await api.post(ApiV1Endpoints.LOGIN, { username: email, password })
    const data = payloadOf(response)
    auth.setTokens(
      typeof data.access_token === 'string' ? data.access_token : null,
      typeof data.refresh_token === 'string' ? data.refresh_token : null,
    )
    return { data: { user: data.user as AuthUser } }
  }

  async function requestPasswordReset(email: string) {
    await api.post(ApiV1Endpoints.AUTH_FORGOT_PASSWORD, { email })
    return { data: { sent: true } }
  }

  async function verifyPasswordResetCode(email: string, code: string) {
    await api.post(ApiV1Endpoints.AUTH_RESET_VERIFY, { email, code })
    return { data: { verified: true } }
  }

  async function resendPasswordResetCode(email: string) {
    await api.post(ApiV1Endpoints.AUTH_RESET_RESEND, { email })
    return { data: { sent: true } }
  }

  async function resetPasswordWithCode(input: {
    email: string
    code: string
    password: string
    passwordConfirmation: string
  }) {
    await api.post(ApiV1Endpoints.AUTH_RESET_PASSWORD, {
      email: input.email,
      code: input.code,
      password: input.password,
      password_confirmation: input.passwordConfirmation,
    })
    return { data: { reset: true } }
  }

  async function changePassword(input: {
    currentPassword: string
    password: string
    passwordConfirmation: string
  }) {
    await api.post(ApiV1Endpoints.AUTH_CHANGE_PASSWORD, {
      current_password: input.currentPassword,
      password: input.password,
      password_confirmation: input.passwordConfirmation,
    })
    return { data: { changed: true } }
  }

  async function updateProfileAvatar(avatar: string) {
    auth.updateUser({ avatar })
    return { data: { avatar } }
  }

  async function removeProfileAvatar() {
    auth.updateUser({ avatar: undefined })
    return { data: { removed: true } }
  }

  return {
    loginWithCredentials,
    requestPasswordReset,
    verifyPasswordResetCode,
    resendPasswordResetCode,
    resetPasswordWithCode,
    changePassword,
    updateProfileAvatar,
    removeProfileAvatar,
  }
}
