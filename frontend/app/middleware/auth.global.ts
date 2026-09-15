import { useAccessAlert } from '~/composables/common/useAccessAlert'
import { safeInternalPath, sessionHasPermissionData } from '~/utils/auth/session'
import { requiredPagePermissionForPath } from '~/utils/freight/page-access'

const PERMITTED_LANDING_ROUTES = [
  ['/', 'dashboard.view'],
  ['/service-orders', 'operations.service_orders.view'],
  ['/quotations', 'sales.quotations.view'],
  ['/finance/documents', 'finance.financial_documents.view'],
  ['/reports', 'reports.view'],
  ['/administration/users', 'admin.users.view'],
  ['/administration/system-settings', 'settings.app_config.view'],
] as const

export default defineNuxtRouteMiddleware((to, from) => {
  const auth = useAuthStore()
  if (import.meta.client) auth.hydrateClient()
  const { showPermissionDenied } = useAccessAlert()

  const publicPaths = [
    '/auth/login',
    '/auth/forget-password',
    '/auth/verify-code',
    '/auth/reset-password',
  ]
  const isPublicPage = publicPaths.includes(to.path)

  if (!auth.isLoggedIn && !isPublicPage) {
    return navigateTo({
      path: '/auth/login',
      query: { redirect: to.fullPath },
    }, { replace: true })
  }

  if (auth.isLoggedIn && isPublicPage) {
    return navigateTo(safeInternalPath(to.query.redirect) || '/', { replace: true })
  }

  const permission = typeof to.meta.permission === 'string' && to.meta.permission
    ? to.meta.permission
    : requiredPagePermissionForPath(to.path)
  const canEnforcePermissions = !import.meta.server || sessionHasPermissionData(auth.user)
  if (canEnforcePermissions && auth.isLoggedIn && permission && !auth.canAccessPage(permission)) {
    showPermissionDenied({
      requestedPath: to.fullPath,
      permission,
    })

    // Keep the current authorized page when denial happens during navigation.
    if (from.matched.length && from.path !== to.path) return abortNavigation()

    // A direct URL needs an authorized page underneath the global dialog.
    const landing = PERMITTED_LANDING_ROUTES.find(([, required]) => auth.canAccessPage(required))
    if (landing) return navigateTo(landing[0], { replace: true })

    // An account with no usable page returns to sign-in without creating a denial page.
    auth.clearSession()
    return navigateTo('/auth/login', { replace: true })
  }
})
