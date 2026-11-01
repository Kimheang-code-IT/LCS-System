type DocumentActionColor = 'primary' | 'secondary' | 'destructive' | 'success' | 'warning' | 'error' | 'neutral' | 'info' | undefined

type DocumentActionButtonUi = {
  color: 'neutral'
  variant: 'solid'
  /** Exact-hex overrides for the secondary/destructive variants; primary keeps the design tokens. */
  class?: string
}

/**
 * Page-header action button style, sized like the list header's "+ New" button.
 * Three variants, selected by `color`:
 * - `primary` (New, Create, Generate, Save, Submit): dark solid on the design
 *   tokens (`--ui-bg-inverted`), exactly the existing create-button look.
 * - anything else (Refresh, Rebuild, Export, Import, Print, Cancel…): solid
 *   grey secondary, #E5E7EB background with #374151 text/icons.
 * - `error`/`destructive` (Delete, Remove): solid red #DC2626 with white text.
 * The `!` utilities win over Nuxt UI's baked-in solid styles; hover keeps a
 * slightly darker fill and loading/disabled/focus behaviour comes from UButton.
 */
export function documentActionButtonUi(color?: DocumentActionColor): DocumentActionButtonUi {
  if (color === 'primary') return { color: 'neutral', variant: 'solid' }
  if (color === 'error' || color === 'destructive') {
    return { color: 'neutral', variant: 'solid', class: 'bg-[#DC2626]! text-white! hover:bg-[#B91C1C]!' }
  }
  return { color: 'neutral', variant: 'solid', class: 'bg-[#E5E7EB]! text-[#374151]! hover:bg-[#D1D5DB]!' }
}
