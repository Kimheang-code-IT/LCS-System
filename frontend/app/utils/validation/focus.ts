/**
 * First-invalid-field navigation.
 *
 * Every addressable input is tagged with `data-field-key` (its canonical
 * model path). Revealing a field is a two-step contract: the host form supplies
 * `reveal` to open the tab/section that owns the key, then we wait for the
 * render lifecycle to actually produce the element before scrolling and
 * focusing it.
 *
 * Waiting uses `nextTick` plus a small number of animation frames — tied to
 * the browser's paint cycle — never a blind timeout.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

/** Marks the element that owns a canonical model path. */
export const FIELD_KEY_ATTRIBUTE = 'data-field-key'

/** Focusable controls we accept as "the input" for a field wrapper. */
const FOCUSABLE_SELECTOR = [
  'input:not([type="hidden"]):not([disabled])',
  'textarea:not([disabled])',
  'select:not([disabled])',
  'button:not([disabled])[data-field-focus]',
  '[role="combobox"]:not([aria-disabled="true"])',
  '[contenteditable="true"]',
].join(', ')

/** Bounded paint-cycle wait (~10 frames) before giving up on a field. */
const MAX_WAIT_FRAMES = 10

/**
 * Opens the section that owns `key`. Returning `false` means "I do not know
 * this field", which lets the caller skip waiting for a render that will never
 * happen.
 */
export type RevealField = (key: string) => boolean | Promise<boolean>

function escapeAttribute(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(value)
  return value.replace(/["\\]/g, '\\$&')
}

export function fieldElement(key: string): HTMLElement | null {
  if (typeof document === 'undefined') return null
  return document.querySelector<HTMLElement>(`[${FIELD_KEY_ATTRIBUTE}="${escapeAttribute(key)}"]`)
}

/** The control to place the caret in; falls back to the wrapper itself. */
export function focusableWithin(wrapper: HTMLElement): HTMLElement {
  return wrapper.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) || wrapper
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => resolve())
    else setTimeout(resolve, 16)
  })
}

/**
 * Wait until the browser has painted the element, or the budget runs out.
 * Returns the element when it appears, otherwise null.
 */
async function waitForField(key: string, frames = MAX_WAIT_FRAMES): Promise<HTMLElement | null> {
  for (let frame = 0; frame <= frames; frame++) {
    const element = fieldElement(key)
    if (element) return element
    await nextFrame()
  }
  return null
}

export type FocusResult = {
  /** The field that was focused, or null when nothing could be revealed. */
  key: string | null
  /** Keys that had no rendered element even after `reveal` ran. */
  unrevealed: string[]
}

/**
 * Open the section that owns `key`, then scroll to and focus the input.
 *
 * Safe to call from a submit handler: it never steals focus while the user is
 * typing, because callers only invoke it on an explicit save attempt or after
 * the backend rejected the payload.
 */
export async function focusField(key: string, reveal?: RevealField): Promise<boolean> {
  if (!key) return false
  const opened = await reveal?.(key)

  let wrapper = fieldElement(key)
  // Only wait for a render when the field was hidden behind a tab/section.
  if (!wrapper && opened !== false) {
    wrapper = await waitForField(key)
  }
  if (!wrapper) return false

  const control = focusableWithin(wrapper)
  const alreadyFocused = typeof document !== 'undefined' && document.activeElement === control
  if (!alreadyFocused) {
    wrapper.scrollIntoView({ block: 'center', behavior: 'smooth' })
    // Focus after the smooth scroll starts, so the caret does not drag the page.
    await nextFrame()
  }
  if (typeof control.focus === 'function') {
    control.focus({ preventScroll: true })
    if ('select' in control && control instanceof HTMLInputElement) {
      try {
        control.select()
      }
      catch {
        // Not every input type supports select(); ignoring is correct here.
      }
    }
  }
  return true
}

/**
 * Focus the first invalid field in logical form order.
 *
 * `keys` must already be in document order — the caller builds it from the
 * tab/section/field order, not from a hash map, so "first" is predictable.
 */
export async function focusFirstInvalidField(
  keys: readonly string[],
  reveal?: RevealField,
): Promise<FocusResult> {
  const ordered = keys.filter(Boolean)
  const unrevealed: string[] = []

  // Sequential by design: the first field that can actually be rendered wins.
  for (const key of ordered) {
    if (await focusField(key, reveal)) return { key, unrevealed }
    unrevealed.push(key)
  }
  return { key: null, unrevealed }
}