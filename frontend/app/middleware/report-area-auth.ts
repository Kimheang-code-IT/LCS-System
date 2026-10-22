import { FREIGHT_REPORTS } from '~/config/freight-reports'
import { defaultReportPathForUser, reportAreaPermission, reportRoutePermission } from '~/utils/freight/report-access'

export default defineNuxtRouteMiddleware((to) => {
  const area = String(to.params.area || '')
  const slug = String(to.params.slug || '')
  if (!area) return

  const auth = useAuthStore()
  const report = FREIGHT_REPORTS.find(item => item.slug === slug)
  const permission = report ? reportRoutePermission(report) : reportAreaPermission(area)
  if (auth.canAccessPage(permission)) return

  const fallback = defaultReportPathForUser(key => auth.canAccessPage(key))
  if (fallback !== to.fullPath) {
    return navigateTo(fallback, { replace: true })
  }

  return navigateTo('/', { replace: true })
})
