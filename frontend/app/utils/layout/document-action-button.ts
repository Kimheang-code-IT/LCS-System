type DocumentActionColor = 'primary' | 'success' | 'warning' | 'error' | 'neutral' | 'secondary' | 'info' | undefined

type DocumentActionButtonUi = {
  color: 'neutral'
  variant: 'solid'
}

/** Header workflow buttons match the list header's "New …" button: dark solid. */
export function documentActionButtonUi(_color?: DocumentActionColor): DocumentActionButtonUi {
  return { color: 'neutral', variant: 'solid' }
}
