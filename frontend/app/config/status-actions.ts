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
  activate: { labelKey: 'freight.statusActions.activate', icon: 'i-lucide-circle-check', color: 'success' },
  deactivate: { labelKey: 'freight.statusActions.deactivate', icon: 'i-lucide-circle-off', color: 'warning' },
  mark: { labelKey: 'freight.statusActions.mark', icon: 'i-lucide-circle-dot', color: 'neutral' },
  finish: { labelKey: 'freight.statusActions.finish', icon: 'i-lucide-flag', color: 'primary' },
  issue: { labelKey: 'freight.statusActions.issue', icon: 'i-lucide-send', color: 'primary' },
  post: { labelKey: 'freight.statusActions.post', icon: 'i-lucide-check-circle-2', color: 'primary' },
  reverse: { labelKey: 'freight.statusActions.reverse', icon: 'i-lucide-undo-2', color: 'warning' },
  close: { labelKey: 'freight.statusActions.close', icon: 'i-lucide-lock', color: 'warning' },
  reopen: { labelKey: 'freight.statusActions.reopen', icon: 'i-lucide-lock-open', color: 'primary' },
  send: { labelKey: 'freight.statusActions.send', icon: 'i-lucide-send', color: 'primary' },
  accept: { labelKey: 'freight.statusActions.accept', icon: 'i-lucide-check', color: 'success' },
  reject: { labelKey: 'freight.statusActions.reject', icon: 'i-lucide-x', color: 'error' },
  cancel: { labelKey: 'freight.statusActions.cancel', icon: 'i-lucide-ban', color: 'warning' },
  convert: { labelKey: 'freight.statusActions.convert', icon: 'i-lucide-arrow-right', color: 'primary' },
  change: { labelKey: 'freight.ui.changeStatus', icon: 'i-lucide-circle-dot', color: 'neutral' },
}
