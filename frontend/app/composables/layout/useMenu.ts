import type { NavigationMenuItem } from '@nuxt/ui'
import { FREIGHT_REPORTS, freightReportPath } from '~/config/freight-reports'
import { requiredPagePermissionForPath } from '~/utils/freight/page-access'
import { reportRoutePermission } from '~/utils/freight/report-access'

const SIDEBAR_COLLAPSED_KEY = 'lcs-freight:sidebar:collapsed'
const SIDEBAR_AUTO_MQ = '(max-width: 1023px)'

/** Single source of truth for the LCS Freight Forwarding navigation. */
export function useMenu() {
  const { t, te } = useI18n()
  const open = useState('sidebar-open', () => false)
  const collapsed = useState('sidebar-collapsed', () => false)
  const manualCollapsed = useState<boolean | null>('sidebar-collapsed-manual', () => null)
  const isNarrow = useMediaQuery(SIDEBAR_AUTO_MQ)
  const hydrated = useState('sidebar-collapsed-hydrated', () => false)

  function close() { open.value = false }
  function applyAutoCollapse(narrow: boolean) { collapsed.value = manualCollapsed.value == null ? narrow : manualCollapsed.value }
  function setCollapsed(value: boolean) {
    collapsed.value = value
    manualCollapsed.value = value
    if (import.meta.client) localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
  }

  if (import.meta.client && !hydrated.value) {
    hydrated.value = true
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    if (saved === '1' || saved === '0') {
      manualCollapsed.value = saved === '1'
      collapsed.value = manualCollapsed.value
    }
    else applyAutoCollapse(isNarrow.value)
    watch(isNarrow, applyAutoCollapse)
  }

  const pageLink = (label: string, to: string): NavigationMenuItem => ({ label, to, exact: true, class: 'text-sm gap-2', onSelect: close })

  const reportLinks = (group: 'operations' | 'finance') =>
    FREIGHT_REPORTS
      .filter(report => report.group === group)
      .map((report) => {
        const label = te(report.titleKey) ? t(report.titleKey) : report.title
        return pageLink(label, freightReportPath(report))
      })

  const ROUTE_PERMISSION: Record<string, string> = {
    '/': 'dashboard.view',
    '/quotations': 'sales.quotations.view',
    '/service-orders': 'operations.service_orders.view',
    '/service-charges': 'finance.service_charges.view',
    '/finance/documents': 'finance.financial_documents.view',
    '/finance/chart-of-accounts': 'finance.accounting.view',
    '/finance/financial-accounts': 'finance.accounting.view',
    '/finance/journals': 'finance.accounting.view',
    '/finance/accounting-periods': 'finance.accounting.view',
    ...Object.fromEntries(
      FREIGHT_REPORTS.map(report => [freightReportPath(report), reportRoutePermission(report)]),
    ),
    '/master-data/business-parties': 'master.reference.view',
    '/master-data/places': 'master.reference.view',
    '/master-data/trade-directions': 'master.reference.view',
    '/master-data/container-types': 'master.reference.view',
    '/master-data/transport-types': 'master.reference.view',
    '/master-data/transport-assets': 'master.reference.view',
    '/master-data/fee-types': 'master.reference.view',
    '/configuration/component-templates': 'configuration.manage',
    '/configuration/component-groups': 'configuration.manage',
    '/configuration/trade-direction-components': 'configuration.manage',
    '/configuration/service-order-tabs': 'configuration.manage',
    '/administration/users': 'admin.users.view',
    '/administration/roles': 'admin.roles.view',
    '/administration/audit-logs': 'admin.audit_logs.view',
    '/administration/document-sequences': 'configuration.manage',
    '/administration/system-settings': 'settings.app_config.view',
  }

  const auth = useAuthStore()

  function canSee(to: string) {
    const pathPermission = requiredPagePermissionForPath(to)
    if (pathPermission) return auth.canAccessPage(pathPermission)
    const permission = ROUTE_PERMISSION[to]
    if (!permission) return true
    return auth.canAccessPage(permission)
  }

  function filterItem(item: NavigationMenuItem): NavigationMenuItem | null {
    if (item.children?.length) {
      const children = item.children.map(filterItem).filter((child): child is NavigationMenuItem => Boolean(child))
      if (!children.length) return null
      return { ...item, children }
    }
    const to = typeof item.to === 'string' ? item.to : ''
    return canSee(to) ? item : null
  }

  const group = (id: string, label: string, icon: string, children: NavigationMenuItem[]): NavigationMenuItem => ({
    label,
    icon,
    type: 'trigger',
    value: id,
    defaultOpen: true,
    class: 'mt-1 text-sm gap-2',
    children,
  })

  const links = computed<NavigationMenuItem[][]>(() => {
    const tree: NavigationMenuItem[] = [
      { label: t('freight.nav.dashboard'), icon: 'i-lucide-layout-dashboard', to: '/', exact: true, class: 'text-sm gap-2', onSelect: close },
      { label: t('freight.nav.quotations'), icon: 'i-lucide-file-check-2', to: '/quotations', class: 'text-sm gap-2', onSelect: close },
      { label: t('freight.pages.serviceOrders'), icon: 'i-lucide-briefcase', to: '/service-orders', class: 'text-sm gap-2', onSelect: close },
      { label: t('freight.pages.serviceCharges'), icon: 'i-lucide-receipt-text', to: '/service-charges', class: 'text-sm gap-2', onSelect: close },
      group('finance', t('freight.nav.finance'), 'i-lucide-banknote', [
        pageLink(t('freight.pages.financialDocuments'), '/finance/documents'),
        pageLink(t('freight.pages.chartOfAccounts'), '/finance/chart-of-accounts'),
        pageLink(t('freight.pages.financialAccounts'), '/finance/financial-accounts'),
        pageLink(t('freight.pages.journals'), '/finance/journals'),
        pageLink(t('freight.pages.accountingPeriods'), '/finance/accounting-periods'),
      ]),
      group('operations-reports', 'Operations Reports', 'i-lucide-chart-no-axes-column-increasing', reportLinks('operations')),
      group('financial-reports', 'Financial Reports', 'i-lucide-chart-no-axes-combined', reportLinks('finance')),
      group('master', t('freight.nav.master'), 'i-lucide-database', [
        pageLink(t('freight.pages.businessParties'), '/master-data/business-parties'),
        pageLink(t('freight.pages.places'), '/master-data/places'),
        pageLink(t('freight.pages.tradeDirections'), '/master-data/trade-directions'),
        pageLink(t('freight.pages.containerTypes'), '/master-data/container-types'),
        pageLink(t('freight.pages.transportTypes'), '/master-data/transport-types'),
        pageLink(t('freight.pages.transportAssets'), '/master-data/transport-assets'),
        pageLink(t('freight.pages.feeTypes'), '/master-data/fee-types'),
      ]),
      group('configuration', t('freight.nav.configuration'), 'i-lucide-blocks', [
        pageLink(t('freight.pages.componentGroups'), '/configuration/component-groups'),
        pageLink(t('freight.pages.componentTemplates'), '/configuration/component-templates'),
        pageLink(t('freight.pages.tradeDirectionComponents'), '/configuration/trade-direction-components'),
        pageLink(t('freight.pages.serviceOrderTabs'), '/configuration/service-order-tabs'),
      ]),
      group('administration', t('freight.nav.administration'), 'i-lucide-shield-check', [
        pageLink(t('freight.pages.users'), '/administration/users'),
        pageLink(t('freight.pages.roles'), '/administration/roles'),
        pageLink(t('freight.pages.documentSequences'), '/administration/document-sequences'),
        pageLink(t('freight.pages.settings'), '/administration/system-settings'),
        pageLink(t('freight.pages.auditLogs'), '/administration/audit-logs'),
      ]),
    ]
    return [tree.map(filterItem).filter((item): item is NavigationMenuItem => Boolean(item)), []]
  })

  return { open, collapsed, links, close, setCollapsed }
}
