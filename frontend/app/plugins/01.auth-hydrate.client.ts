import { normalizeRoutePath, safeInternalPath } from '~/utils/auth/session'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { usePreferencesStore } from '~/stores/preferences'

const AUTH_PUBLIC_PATHS = new Set([
  '/auth/login',
  '/auth/forget-password',
  '/auth/verify-code',
  '/auth/reset-password',
])

export default defineNuxtPlugin(async () => {
  const auth = useAuthStore()
  auth.hydrateClient()
  const localization = useAppLocalization()
  const preferences = usePreferencesStore()

  if (auth.isLoggedIn) await localization.load()
  await preferences.hydrate()

  watch(() => auth.isLoggedIn, async (loggedIn) => {
    if (!loggedIn) return
    await localization.load(true)
    preferences.syncLocaleWithConfig()
  })

  const route = useRoute()
  if (auth.isLoggedIn && AUTH_PUBLIC_PATHS.has(normalizeRoutePath(route.path))) {
    void navigateTo(safeInternalPath(route.query.redirect) || '/', { replace: true })
  }
})
