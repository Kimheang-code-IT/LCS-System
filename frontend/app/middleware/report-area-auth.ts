import { useAccessAlert } from '~/composables/common/useAccessAlert'
import { defaultReportPathForUser, reportAreaPermission } from '~/utils/freight/report-access'

export default defineNuxtRouteMiddleware((to) => {
  const area = String(to.params.area || '')
  if (!area) return

  const auth = useAuthStore()
  const permission = reportAreaPermission(area)
  if (auth.canAccessPage(permission)) return

  const { showPermissionDenied } = useAccessAlert()
  showPermissionDenied({
    requestedPath: to.fullPath,
    permission,
  })

  const fallback = defaultReportPathForUser(key => auth.canAccessPage(key))
  if (fallback !== to.fullPath) {
    return navigateTo(fallback, { replace: true })
  }

  return navigateTo('/', { replace: true })
})
