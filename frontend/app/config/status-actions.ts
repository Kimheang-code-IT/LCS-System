/**
 * How each record-status verb is drawn in the row "..." menu.
 *
 * The backend policy decides *which* transitions exist and for whom; this only
 * decides label, icon and tone. It lives in `app/config` (not in the utils that
 * consume it) because the Nuxt icon client bundle only scans
 * `app/{components,composables,config,layouts,pages}` — an icon named only in
 * `app/utils` would never be bundled.
 */
export type StatusActionColor = 'primary' | 'neutral' | 'success' | 'warning' | 'error'

export interface StatusActionMeta {
  labelKey: string
  icon: string
  color: StatusActionColor
}

export const STATUS_ACTION_META: Record<string, StatusActionMeta> = {
  activate: { labelKey: 'freight.statusActions.activate', icon: 'i-lucide-circle-check', color: 'neutral' },
  deactivate: { labelKey: 'freight.statusActions.deactivate', icon: 'i-lucide-circle-off', color: 'neutral' },
  mark: { labelKey: 'freight.statusActions.mark', icon: 'i-lucide-circle-dot', color: 'neutral' },
  finish: { labelKey: 'freight.statusActions.finish', icon: 'i-lucide-flag', color: 'neutral' },
  issue: { labelKey: 'freight.statusActions.issue', icon: 'i-lucide-send', color: 'neutral' },
  post: { labelKey: 'freight.statusActions.post', icon: 'i-lucide-check-circle-2', color: 'neutral' },
  reverse: { labelKey: 'freight.statusActions.reverse', icon: 'i-lucide-undo-2', color: 'neutral' },
  close: { labelKey: 'freight.statusActions.close', icon: 'i-lucide-lock', color: 'neutral' },
  open: { labelKey: 'freight.statusActions.open', icon: 'i-lucide-lock-open', color: 'neutral' },
  reopen: { labelKey: 'freight.statusActions.reopen', icon: 'i-lucide-lock-open', color: 'neutral' },
  send: { labelKey: 'freight.statusActions.send', icon: 'i-lucide-send', color: 'neutral' },
  accept: { labelKey: 'freight.statusActions.accept', icon: 'i-lucide-check', color: 'neutral' },
  reject: { labelKey: 'freight.statusActions.reject', icon: 'i-lucide-x', color: 'neutral' },
  cancel: { labelKey: 'freight.statusActions.cancel', icon: 'i-lucide-ban', color: 'neutral' },
  convert: { labelKey: 'freight.statusActions.convert', icon: 'i-lucide-arrow-right', color: 'neutral' },
  // Fallback metadata for a verb the backend emits that has no specific entry;
  // it is never offered as a menu item of its own.
  change: { labelKey: 'freight.ui.changeStatus', icon: 'i-lucide-circle-dot', color: 'neutral' },
}
