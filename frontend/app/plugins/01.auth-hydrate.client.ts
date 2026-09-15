import { safeInternalPath } from '~/utils/auth/session'

const AUTH_PUBLIC_PATHS = new Set([
  '/auth/login',
  '/auth/forget-password',
  '/auth/verify-code',
  '/auth/reset-password',
])

export default defineNuxtPlugin(() => {
  const auth = useAuthStore()
  auth.hydrateClient()

  const route = useRoute()
  if (auth.isLoggedIn && AUTH_PUBLIC_PATHS.has(route.path)) {
    void navigateTo(safeInternalPath(route.query.redirect) || '/', { replace: true })
  }
})
