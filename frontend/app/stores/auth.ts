import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthUser } from '~/types/auth-user'
import { AUTH_STORAGE_KEY, compactAuthUser } from '~/utils/auth/session'

function restoreSessionUser(candidate: AuthUser | null | undefined): AuthUser | null {
  if (!candidate?.email) return null
  return candidate
}

const ACCESS_TOKEN_KEY = 'lcs-access-token'
const REFRESH_TOKEN_KEY = 'lcs-refresh-token'

export const useAuthStore = defineStore('auth', () => {
  const cookieUser = useCookie<AuthUser | null>('auth_user', {
    default: () => null,
    path: '/',
    sameSite: 'lax',
    secure: import.meta.env.PROD,
    maxAge: 60 * 60 * 24 * 30,
  })
  const storedUser = ref<AuthUser | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const clientHydrated = ref(false)
  const user = computed(() => storedUser.value || cookieUser.value)
  const isLoggedIn = computed(() => Boolean(user.value?.email))

  function persist(userData: AuthUser | null) {
    storedUser.value = userData
    cookieUser.value = userData ? compactAuthUser(userData) : null
    if (!import.meta.client) return
    if (userData) localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(userData))
    else localStorage.removeItem(AUTH_STORAGE_KEY)
  }

  function hydrateClient() {
    if (!import.meta.client) return

    if (!accessToken.value) {
      accessToken.value = localStorage.getItem(ACCESS_TOKEN_KEY)
      refreshToken.value = localStorage.getItem(REFRESH_TOKEN_KEY)
    }

    let resolved: AuthUser | null = null
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY)
      resolved = raw ? JSON.parse(raw) as AuthUser : null
    }
    catch {
      localStorage.removeItem(AUTH_STORAGE_KEY)
    }

    if (!resolved?.email && cookieUser.value?.email) {
      resolved = cookieUser.value
    }

    resolved = restoreSessionUser(resolved)
    if (resolved?.email) {
      persist(resolved)
    }

    clientHydrated.value = true
  }

  function login(userData: AuthUser) {
    persist(userData)
  }

  function setTokens(access: string | null, refresh: string | null) {
    accessToken.value = access
    refreshToken.value = refresh
    if (!import.meta.client) return
    if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access)
    else localStorage.removeItem(ACCESS_TOKEN_KEY)
    if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
    else localStorage.removeItem(REFRESH_TOKEN_KEY)
  }

  function clearSession() {
    persist(null)
    setTokens(null, null)
    clientHydrated.value = true
  }

  async function logout() {
    clearSession()
    await navigateTo('/auth/login')
  }

  /**
   * Frontend-only visibility check. Backend must still enforce authorization.
   * `permissions` is authoritative when present. `pageAccess` remains a
   * backwards-compatible fallback for older sessions.
   */
  function canAccessPage(pageId: string): boolean {
    const currentUser = user.value
    if (!currentUser) return false
    if (currentUser.role === 'SuperAdmin') return true
    if (currentUser.pageAccess?.includes('ALL_PAGES')) return true

    if (Array.isArray(currentUser.permissions)) {
      if (currentUser.permissions.includes('ALL_PAGES')) return true
      if (currentUser.permissions.includes(pageId)) return true
      if (pageId === 'configuration.manage' && currentUser.permissions.includes('configuration.configure')) return true
      return false
    }

    const access = currentUser.pageAccess
    if (!access?.length) return true
    return access.includes(pageId)
  }

  function updateUser(partial: Partial<AuthUser>) {
    if (!user.value) return
    const next = { ...user.value, ...partial }
    if ('avatar' in partial && partial.avatar == null) {
      delete next.avatar
    }
    persist(next)
  }

  return {
    user,
    isLoggedIn,
    clientHydrated,
    accessToken,
    refreshToken,
    login,
    setTokens,
    hydrateClient,
    clearSession,
    logout,
    updateUser,
    canAccessPage,
  }
})
