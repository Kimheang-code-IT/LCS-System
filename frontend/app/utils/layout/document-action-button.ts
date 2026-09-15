type DocumentActionColor = 'primary' | 'success' | 'warning' | 'error' | 'neutral' | 'secondary' | 'info' | undefined

type DocumentActionButtonUi = {
  color: 'primary' | 'success' | 'neutral'
  variant: 'solid' | 'outline'
}

/** ERPNext-like header buttons: outline for secondary, solid for primary workflow CTAs. */
export function documentActionButtonUi(color?: DocumentActionColor): DocumentActionButtonUi {
  if (color === 'primary') return { color: 'primary', variant: 'solid' }
  if (color === 'success') return { color: 'success', variant: 'solid' }
  return { color: 'neutral', variant: 'outline' }
}
