export type HeaderListNavDirection = 'previous' | 'next' | null

/** Previous/next are locked while creating, at list ends, or while a nav request is in flight. */
export function headerListNavDisabled(options: {
  isCreate: boolean
  canNavigate: boolean
  loading: boolean
  direction: HeaderListNavDirection
}): boolean {
  return options.isCreate || !options.canNavigate || options.loading || Boolean(options.direction)
}

/**
 * Header chrome (title/breadcrumbs/badges) belongs to `chromeRoute` when a page on
 * that route last wrote it. A leaving page must not clear chrome that a page on the
 * current route already claimed — otherwise navigating between pages with the same
 * route `titleKey` (e.g. reports) drops the new title.
 */
export function headerChromeOwnedByCurrentRoute(chromeRoute: string, currentRoute: string): boolean {
  return Boolean(chromeRoute) && chromeRoute === currentRoute
}

