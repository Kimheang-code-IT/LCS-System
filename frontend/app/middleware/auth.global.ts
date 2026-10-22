import { useSetup } from '~/composables/auth/useSetup'
import { normalizeRoutePath, safeInternalPath, sessionHasPermissionData } from '~/utils/auth/session'
import { pagePermissionCandidatesForPath } from '~/utils/freight/page-access'

const PERMITTED_LANDING_ROUTES = [
  ['/', 'dashboard.view'],
  ['/service-orders', 'operations.service_orders.view'],
  ['/quotations', 'sales.quotations.view'],
  ['/service-charges', 'finance.service_charges.view'],
  ['/finance/documents', 'finance.financial_documents.view'],
  ['/reports', 'reports.service_order_register.view'],
  ['/administration/users', 'admin.users.view'],
  ['/administration/system-settings', 'settings.app_config.view'],
] as const

const SETUP_PATH = '/auth/setup'
/** Where an administrator-set password has to be replaced before anything else. */
const FORCED_PASSWORD_PATH = '/auth/change-password'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const auth = useAuthStore()
  if (import.meta.client) auth.hydrateClient()
  const routePath = normalizeRoutePath(to.path)

  const publicPaths = [
    '/auth/login',
    '/auth/forget-password',
    '/auth/verify-code',
    '/auth/reset-password',
  ]
  const isSetupPage = routePath === SETUP_PATH
  const isPublicPage = publicPaths.includes(routePath) || isSetupPage

  // A freshly migrated (or reset) database has no users: route to first-run setup.
  // A failing probe must not abort navigation, so fall back to the last safe answer.
  let setupRequired = false
  if (import.meta.client) {
    try {
      setupRequired = await useSetup().refresh()
    }
    catch {
      setupRequired = false
    }
  }
  if (setupRequired) {
    if (!isSetupPage) return navigateTo(SETUP_PATH, { replace: true })
    // A stale cookie must not present a logged-in shell while setup is required.
    if (auth.isLoggedIn) auth.clearSession()
    return
  }
  if (isSetupPage) {
    return navigateTo(auth.isLoggedIn ? '/' : '/auth/login', { replace: true })
  }

  if (!auth.isLoggedIn && !isPublicPage) {
    return navigateTo({
      path: '/auth/login',
      query: { redirect: to.fullPath },
    }, { replace: true })
  }

  if (auth.isLoggedIn && isPublicPage) {
    return navigateTo(safeInternalPath(to.query.redirect) || '/', { replace: true })
  }

  // A password an administrator set has to be replaced before anything else.
  // The API refuses every other route while it stands, so letting the user
  // through here would only produce a screen full of failed requests.
  if (auth.isLoggedIn) {
    const mustChange = auth.user?.mustChangePassword === true
    if (mustChange && routePath !== FORCED_PASSWORD_PATH) {
      return navigateTo(FORCED_PASSWORD_PATH, { replace: true })
    }
    if (!mustChange && routePath === FORCED_PASSWORD_PATH) {
      return navigateTo('/', { replace: true })
    }
  }

  // Role and permission changes are authoritative immediately on the API.
  // Refresh the lightweight identity snapshot during navigation so menus and
  // route guards converge without requiring the user to sign out.
  if (import.meta.client && auth.isLoggedIn) await auth.refreshSession()

  // The route map is authoritative; page meta is only a fallback for screens
  // outside it. Legacy codes stay accepted while old sessions age out.
  const pathPermissions = pagePermissionCandidatesForPath(routePath)
  const metaPermission = typeof to.meta.permission === 'string' && to.meta.permission
    ? [to.meta.permission]
    : []
  const permissions = pathPermissions.length ? pathPermissions : metaPermission
  const canEnforcePermissions = !import.meta.server || sessionHasPermissionData(auth.user)
  if (canEnforcePermissions && auth.isLoggedIn && permissions.length && !auth.canAccessAnyPage(permissions)) {
    // Keep the current authorized page when denial happens during navigation.
    if (from.matched.length && from.path !== to.path) return abortNavigation()

    // A direct URL needs an authorized page underneath.
    const landing = PERMITTED_LANDING_ROUTES.find(([, required]) => auth.canAccessPage(required))
    if (landing) return navigateTo(landing[0], { replace: true })

    // An account with no usable page returns to sign-in without creating a denial page.
    auth.clearSession()
    return navigateTo('/auth/login', { replace: true })
  }
})
