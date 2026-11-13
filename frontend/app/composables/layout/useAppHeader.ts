import type { DropdownMenuItem } from '@nuxt/ui'
import { shallowRef } from 'vue'
import { headerChromeOwnedByCurrentRoute } from '~/utils/layout/header-actions'

export type AppHeaderBreadcrumb = {
  label: string
  to?: string
  icon?: string
}

export type AppHeaderCreateButton = {
  label: string
  icon?: string
  onClick: () => void
}

export type AppHeaderListNavConfig = {
  listTo?: string
  listLabel: string
  previousLabel: string
  nextLabel: string
  previousDisabled: boolean
  nextDisabled: boolean
  previousLoading: boolean
  nextLoading: boolean
  onPrevious?: () => void
  onNext?: () => void
}

export type AppHeaderSaveConfig = {
  label: string
  loading?: boolean
  onClick: () => void
}

export type AppHeaderCancelConfig = {
  label: string
  to?: string
  onClick?: () => void
}

export type AppHeaderActionsConfig = {
  /** Opt-in: only list pages that support create should set true. */
  canCreate: boolean
  createLabel: string
  createIcon?: string
  /** When set, renders these instead of the single create button. */
  createButtons?: AppHeaderCreateButton[]
  refreshing?: boolean
  moreItems?: DropdownMenuItem[][]
  listNav?: AppHeaderListNavConfig
  save?: AppHeaderSaveConfig
  cancel?: AppHeaderCancelConfig
  onCreate?: () => void
  onRefresh?: () => void | Promise<void>
}

/**
 * Client-only shared ref — must NOT use useState.
 * Actions include functions that Nuxt cannot SSR-serialize.
 */
const headerActions = shallowRef<AppHeaderActionsConfig | null>(null)
/** Prevents an unmounting page from clearing the next page's actions. */
let actionsOwnerId = 0
/**
 * Last component instance that wrote the shared title/breadcrumb/badge chrome.
 * A page leaving during a route change can still have its own watchers fire for
 * the *new* route; without this, its unmount `clear()` wipes the chrome the
 * destination page already wrote (list → detail showed no record number).
 */
let chromeOwnerId = 0
/** Monotonic instance counter so every component gets a distinct chrome id. */
let chromeInstanceSeq = 0

/**
 * Shared dynamic header state for layout AppHeader.
 * Create is opt-in via setActions({ canCreate: true }).
 */
export function useAppHeader() {
  const title = useState('app-header-title', () => '')
  const breadcrumbs = useState<AppHeaderBreadcrumb[]>('app-header-breadcrumbs', () => [])
  const route = useRoute()
  const { t, te } = useI18n()
  /**
   * Route this component instance last wrote chrome for. A page that is being
   * unmounted by a navigation must not wipe the chrome the *new* page already
   * wrote (the classic list → detail race: the leaving list cleared the detail
   * breadcrumb and the detail never re-wrote it).
   */
  let ownedRoute = ''

  /** Identity of this composable instance in the shared chrome-owner slot. */
  const chromeInstance = ++chromeInstanceSeq

  const metaTitle = computed(() => {
    const key = route.meta.titleKey
    if (typeof key !== 'string' || !key) return ''
    return te(key) ? t(key) : key
  })

  const displayTitle = computed(() => title.value || metaTitle.value)
  const hasBreadcrumbs = computed(() => breadcrumbs.value.length > 0)

  function claim() {
    ownedRoute = route.fullPath
    chromeOwnerId = chromeInstance
  }

  function setTitle(value: string) {
    claim()
    title.value = value
    breadcrumbs.value = []
  }

  function setBreadcrumbs(items: AppHeaderBreadcrumb[]) {
    claim()
    breadcrumbs.value = items
    const last = items[items.length - 1]
    if (last?.label) title.value = last.label
  }

  /** Register header actions; returns an owner id for safe clear on unmount. */
  function setActions(config: AppHeaderActionsConfig | null): number {
    const id = ++actionsOwnerId
    headerActions.value = config
    return id
  }

  function clearActions(ownerId?: number) {
    if (ownerId != null && ownerId !== actionsOwnerId) return
    headerActions.value = null
  }

  /**
   * Clear title/breadcrumb/badge chrome only.
   * Do NOT clear actions here — unmount order races with the next page’s
   * AppHeaderPageActions.setActions(); actions use clearActions(ownerId).
   *
   * Unmount order also races with the next page's setTitle/setBreadcrumbs. When a
   * page on the current route has already claimed the chrome, this leaving page
   * must not wipe it. Without this, navigating between report pages drops the new
   * title and the header falls back to the generic route `titleKey` (e.g. "Reports").
   */
  function clear() {
    // Only the page that wrote this route's chrome may clear it, and only while
    // it is still the last writer: a leaving page's watchers can fire for the
    // destination route during the same navigation.
    if (chromeOwnerId !== chromeInstance) return
    if (!headerChromeOwnedByCurrentRoute(ownedRoute, route.fullPath)) return
    title.value = ''
    breadcrumbs.value = []
    ownedRoute = ''
    chromeOwnerId = 0
  }

  /** @deprecated use clear() */
  function clearTitle() {
    clear()
  }

  return {
    title,
    breadcrumbs,
    actions: headerActions,
    displayTitle,
    hasBreadcrumbs,
    setTitle,
    setBreadcrumbs,
    setActions,
    clearActions,
    clear,
    clearTitle,
  }
}
