import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthUser } from '~/types/api'
import { AUTH_STORAGE_KEY, compactAuthUser } from '~/utils/auth/session'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { csrfRequestHeaders } from '~/utils/security/csrf'
import { authErrorCode, authErrorStatus, createRenewalCoordinator, renewalLeadMillis, type SessionResponse } from '~/utils/auth/renewal'

const SESSION_EVENT = 'lcs-session-event'
type SessionEvent = { kind: 'renewed' | 'logout', id: string, expiresAt?: number }

export const useAuthStore = defineStore('auth', () => {
  const config = useRuntimeConfig()
  const cookieUser = useCookie<AuthUser | null>('auth_user', { default: () => null, path: '/', sameSite: 'lax', secure: import.meta.env.PROD })
  const storedUser = ref<AuthUser | null>(null)
  const accessToken = ref<string | null>(null)
  const expiresAt = ref(0)
  const restoring = ref(true)
  const sessionExpired = ref(false)
  const connectionProblem = ref(false)
  const logoutFailed = ref(false)
  const accountChanged = ref(false)
  const identityUnverified = ref(false)
  let renewAt = 0
  let identityCheck: Promise<void> | null = null
  const user = computed(() => storedUser.value || cookieUser.value)
  const isLoggedIn = computed(() => Boolean(user.value?.email) && !sessionExpired.value)
  const baseURL = String(config.public.apiBase || '')
  let restorePromise: Promise<void> | null = null
  let initialized = false
  let restored = false
  let channel: BroadcastChannel | undefined
  let lastPermissionRefreshAt = 0
  let permissionRefresh: Promise<void> | null = null
  let activityAt = 0
  let activitySentAt = 0
  let epoch = 0
  let lastEventId = ''
  let identityVersion = 0

  function storageGet(key: string): string | null {
    try { return localStorage.getItem(key) }
    catch { return null }
  }
  function storageSet(key: string, value: string | null) {
    try {
      if (value === null) localStorage.removeItem(key)
      else localStorage.setItem(key, value)
    }
    catch { /* Cookie sessions still work with browser storage disabled. */ }
  }
  function persist(data: AuthUser | null) {
    storedUser.value = data
    cookieUser.value = data ? compactAuthUser(data) : null
    if (import.meta.client) storageSet(AUTH_STORAGE_KEY, data ? JSON.stringify(data) : null)
  }
  function eventSnapshot(): SessionEvent | null {
    try { return JSON.parse(storageGet(SESSION_EVENT) || 'null') as SessionEvent | null }
    catch { return null }
  }
  function publish(kind: SessionEvent['kind'], expiration = expiresAt.value) {
    const event: SessionEvent = { kind, id: crypto.randomUUID(), expiresAt: expiration }
    storageSet(SESSION_EVENT, JSON.stringify(event))
    channel?.postMessage(event)
  }
  async function withRefreshLock<T>(work: () => Promise<T>): Promise<T> {
    if (import.meta.client && navigator.locks) return navigator.locks.request('lcs-auth-refresh', work)
    return work()
  }
  function csrfHeaders() {
    return { 'X-Requested-With': 'XMLHttpRequest', ...csrfRequestHeaders('POST', String(config.public.csrfCookieName), String(config.public.csrfHeaderName)) }
  }
  function expire() {
    sessionExpired.value = true
    accessToken.value = null
    connectionProblem.value = false
  }
  async function fetchIdentity(): Promise<AuthUser> {
    const response = await $fetch<{ data: AuthUser }>(ApiV1Endpoints.AUTH_ME, { baseURL, credentials: 'include', retry: 0, timeout: 10000 })
    return response.data
  }
  const renewal = createRenewalCoordinator({
    request: async () => {
      const before = eventSnapshot()?.id
      return withRefreshLock(async () => {
        const current = eventSnapshot()
        if (current?.kind === 'logout') throw { statusCode: 401 }
        // A sibling tab already rotated while we waited. The HttpOnly access
        // cookie is shared; no credentials need to cross the channel or storage.
        if (current?.id !== before && current?.expiresAt && current.expiresAt * 1000 > Date.now()) {
          return { user: await fetchIdentity(), expires_at: current.expiresAt }
        }
        const request = async () => {
          const response = await $fetch<{ data: SessionResponse }>(ApiV1Endpoints.REFRESH, {
            baseURL, method: 'POST', body: {}, credentials: 'include', headers: csrfHeaders(), retry: 0, timeout: 10000,
          })
          if (eventSnapshot()?.kind === 'logout') throw { statusCode: 401 }
          publish('renewed', response.data.expires_at)
          return response.data
        }
        try { return await request() }
        catch (error) {
          if (authErrorCode(error) !== 'REFRESH_CONFLICT') throw error
          // No stale credential is ever replayed: re-read cookies once after
          // the overlapping response has had a chance to arrive.
          await new Promise(resolve => setTimeout(resolve, 300))
          return request()
        }
      })
    },
    apply: data => {
      acceptSession(data)
    },
    expired: expire,
    unavailable: () => { connectionProblem.value = true },
    isActive: () => import.meta.client && document.visibilityState === 'visible' && Date.now() - activityAt < 120000,
  })

  function setExpiry(expiration: number) {
    expiresAt.value = expiration
    const remaining = expiration * 1000 - Date.now()
    renewAt = expiration * 1000 - renewalLeadMillis(remaining)
  }
  function acceptSession(data: SessionResponse) {
    if (restored && user.value && data.user && String(data.user.id) !== String(user.value.id)) {
      accountChanged.value = true
      renewal.invalidate()
      expire()
      return
    }
    accessToken.value = data.access_token || null
    setExpiry(data.expires_at)
    identityUnverified.value = false
    sessionExpired.value = false
    connectionProblem.value = false
    if (data.user) persist({ ...user.value, ...data.user })
    renewal.schedule(data.expires_at)
  }
  function receive(event: SessionEvent) {
    if (!event?.id || event.id === lastEventId) return
    lastEventId = event.id
    const identitySequence = ++identityVersion
    if (event?.kind === 'logout') {
      epoch++
      identityCheck = null
      renewal.invalidate()
      expire()
    }
    else if (event?.kind === 'renewed' && event.expiresAt) {
      accessToken.value = null
      identityUnverified.value = true
      const version = epoch
      const wasExpired = sessionExpired.value
      const check = fetchIdentity().then(data => {
        if (version !== epoch || identitySequence !== identityVersion) return
        if (user.value && String(data.id) !== String(user.value.id)) {
          accountChanged.value = true
          renewal.invalidate()
          expire()
          return
        }
        persist({ ...user.value, ...data })
        setExpiry(event.expiresAt!)
        identityUnverified.value = false
        sessionExpired.value = false
        connectionProblem.value = false
        if (wasExpired) renewal.resume()
        renewal.schedule(event.expiresAt!)
      }).catch(() => { if (version === epoch) connectionProblem.value = true }).finally(() => { if (identityCheck === check) identityCheck = null })
      identityCheck = check
    }
  }

  const storageChanged = (event: StorageEvent) => {
    if (event.key === SESSION_EVENT && event.newValue) {
      try { receive(JSON.parse(event.newValue) as SessionEvent) }
      catch { /* Ignore malformed non-authoritative metadata. */ }
    }
  }
  const activity = () => { activityAt = Date.now(); wake() }
  const wake = () => {
    if (isLoggedIn.value && document.visibilityState === 'visible' && Date.now() >= renewAt) void renewal.refresh()
  }
  function hydrateClient() {
    if (!import.meta.client || initialized) return
    initialized = true
    // Remove credentials persisted by earlier releases in either auth mode.
    storageSet('lcs-access-token', null)
    storageSet('lcs-refresh-token', null)
    try {
      const candidate = JSON.parse(storageGet(AUTH_STORAGE_KEY) || 'null') as AuthUser | null
      if (candidate?.email) storedUser.value = candidate
    }
    catch { storageSet(AUTH_STORAGE_KEY, null) }
    if (typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel('lcs-auth')
      channel.onmessage = event => receive(event.data as SessionEvent)
    }
    window.addEventListener('storage', storageChanged)
    window.addEventListener('pointerdown', activity, { passive: true })
    window.addEventListener('keydown', activity)
    window.addEventListener('focus', wake)
    document.addEventListener('visibilitychange', wake)
  }
  function activityHeaders(): Record<string, string> {
    if (activityAt > activitySentAt && Date.now() - activitySentAt > 15000) {
      activitySentAt = Date.now()
      return { 'X-User-Activity': '1' }
    }
    return {}
  }
  function login(data: AuthUser) {
    epoch++
    restored = true
    renewal.resume()
    sessionExpired.value = false
    logoutFailed.value = false
    accountChanged.value = false
    identityUnverified.value = false
    persist(data)
    renewal.schedule(expiresAt.value)
    publish('renewed')
  }
  function setTokens(access: string | null, _refresh: string | null = null, expiration = 0) {
    accessToken.value = access
    setExpiry(expiration)
    renewal.schedule(expiration)
  }
  function clearSession() {
    epoch++
    renewal.invalidate()
    persist(null)
    accessToken.value = null
    expiresAt.value = 0
  }
  async function restoreSession() {
    if (!import.meta.client || restored) return
    if (restorePromise) return restorePromise
    hydrateClient()
    restoring.value = true
    renewal.resume()
    restorePromise = (async () => {
      await renewal.refresh()
      restored = true
      restoring.value = false
    })().finally(() => { restorePromise = null })
    return restorePromise
  }
  async function refreshSession(force = false) {
    if (!import.meta.client || !isLoggedIn.value) return
    if (!force && Date.now() - lastPermissionRefreshAt < 15000) return
    if (permissionRefresh) return permissionRefresh
    const version = epoch
    const identitySequence = identityVersion
    permissionRefresh = (async () => {
      try {
        let data: AuthUser
        try { data = await fetchIdentity() }
        catch (error) {
          if (authErrorCode(error) !== 'ACCESS_TOKEN_EXPIRED') throw error
          if (await renewal.refresh() !== 'renewed') return
          data = await fetchIdentity()
        }
        if (version === epoch && identitySequence === identityVersion && user.value) {
          if (String(data.id) !== String(user.value.id)) {
            blockChangedAccount()
            return
          }
          persist({ ...user.value, ...data, pageAccess: data.permissions || data.pageAccess })
        }
        lastPermissionRefreshAt = Date.now()
      }
      catch (error) {
        if (['SESSION_EXPIRED', 'SESSION_REVOKED', 'SESSION_INVALID'].includes(authErrorCode(error))) expire()
      }
      finally { permissionRefresh = null }
    })()
    return permissionRefresh
  }
  async function logout() {
    epoch++
    identityCheck = null
    renewal.invalidate()
    publish('logout')
    expire()
    await renewal.settle()
    try {
      await withRefreshLock(async () => { await $fetch<unknown>(String(ApiV1Endpoints.LOGOUT), { baseURL, method: 'POST', credentials: 'include', retry: 0, timeout: 10000, headers: csrfHeaders() }); })
      logoutFailed.value = false
    }
    catch (error) {
      if (authErrorStatus(error) === 401) {
        clearSession()
        await navigateTo('/auth/login')
        return
      }
      logoutFailed.value = true
      expire()
      return
    }
    clearSession()
    await navigateTo('/auth/login')
  }
  async function waitForIdentity() {
    while (identityCheck) await identityCheck
  }
  function blockChangedAccount() {
    epoch++
    identityCheck = null
    accountChanged.value = true
    renewal.invalidate()
    expire()
  }
  function disposeSessionListeners() {
    renewal.invalidate()
    channel?.close()
    if (!import.meta.client) return
    window.removeEventListener('storage', storageChanged)
    window.removeEventListener('pointerdown', activity)
    window.removeEventListener('keydown', activity)
    window.removeEventListener('focus', wake)
    document.removeEventListener('visibilitychange', wake)
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
      return currentUser.permissions.includes(pageId)
    }

    // A session without permission data must see nothing until refreshSession()
    // loads it; default-allow would briefly expose every screen.
    const access = currentUser.pageAccess
    if (!access?.length) return false
    return access.includes(pageId)
  }

  function canAccessAnyPage(pageIds: readonly string[]): boolean {
    return pageIds.some(pageId => canAccessPage(pageId))
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
    user, isLoggedIn, accessToken, expiresAt, restoring, sessionExpired, connectionProblem, logoutFailed, accountChanged, identityUnverified,
    login, setTokens, hydrateClient, clearSession, restoreSession, refreshSession, logout,
    updateUser, canAccessPage, canAccessAnyPage, activityHeaders, acceptSession,
    renewAccess: renewal.refresh, expire, disposeSessionListeners, waitForIdentity, blockChangedAccount,
  }
})
