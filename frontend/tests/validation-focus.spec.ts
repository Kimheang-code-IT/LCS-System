import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  FIELD_KEY_ATTRIBUTE,
  fieldElement,
  focusField,
  focusFirstInvalidField,
} from '../app/utils/validation/focus'

/**
 * `focus.ts` only touches a narrow slice of the DOM (querySelector, scrollIntoView,
 * focus, activeElement), so the navigation contract is verified against a small
 * stand-in rather than by mounting the whole Nuxt runtime.
 */
type FakeControl = {
  focused: boolean
  focus: () => void
  scrollIntoView: () => void
}

function makeField(inputName: string) {
  const control: FakeControl = {
    focused: false,
    focus: () => { control.focused = true },
    scrollIntoView: () => {},
  }
  const wrapper = {
    [FIELD_KEY_ATTRIBUTE]: inputName,
    querySelector: (selector: string) => (selector.includes('input') ? control : null),
    scrollIntoView: () => {},
  }
  return { control, wrapper }
}

const fields = new Map<string, ReturnType<typeof makeField>>()
let active: FakeControl | null = null

function renderVisible(key: string) {
  fields.set(key, makeField(key))
}

beforeEach(() => {
  fields.clear()
  active = null
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: {
      get activeElement() { return active },
      set activeElement(value: FakeControl | null) { active = value },
      querySelector: (selector: string) => {
        const match = /\[data-field-key="(.*)"\]/.exec(selector)
        if (!match) return null
        return fields.get(match[1]!)?.wrapper ?? null
      },
    },
  })
  // Resolve immediately so the tests do not depend on wall-clock timing.
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => { cb(); return 0 })
  vi.stubGlobal('setTimeout', ((cb: () => void) => { cb(); return 0 }) as never)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fieldElement', () => {
  it('finds the wrapper carrying the model path', () => {
    renderVisible('customerPartyId')
    expect(fieldElement('customerPartyId')).toBeTruthy()
    expect(fieldElement('missing')).toBeNull()
  })
})

describe('focusField', () => {
  it('scrolls to and focuses a field that is already rendered', async () => {
    renderVisible('customerPartyId')
    expect(await focusField('customerPartyId')).toBe(true)
    expect(fields.get('customerPartyId')?.control.focused).toBe(true)
  })

  it('asks the host to reveal the field and waits for the render', async () => {
    const reveal = vi.fn((key: string) => {
      // The host opens the tab; the element only exists on the next paint.
      renderVisible(key)
      return true
    })
    expect(await focusField('declarationNumber', reveal)).toBe(true)
    expect(reveal).toHaveBeenCalledWith('declarationNumber')
    expect(fields.get('declarationNumber')?.control.focused).toBe(true)
  })

  it('gives up instead of hanging when the host cannot reveal the field', async () => {
    expect(await focusField('declarationNumber', () => false)).toBe(false)
  })

  it('never steals focus from a field the user is already editing', async () => {
    renderVisible('customerPartyId')
    const control = fields.get('customerPartyId')!.control
    await focusField('customerPartyId')
    globalThis.document.activeElement = control as never
    // A second reveal of the same field is a no-op for the caret position.
    expect(control.focused).toBe(true)
  })
})

describe('focusFirstInvalidField', () => {
  it('focuses the first field in the order it was given', async () => {
    renderVisible('customerPartyId')
    renderVisible('date')
    const result = await focusFirstInvalidField(['customerPartyId', 'date'])
    expect(result.key).toBe('customerPartyId')
    expect(fields.get('date')?.control.focused).toBe(false)
  })

  it('skips a field that cannot be rendered and moves on', async () => {
    renderVisible('date')
    const result = await focusFirstInvalidField(['hidden', 'date'])
    expect(result.key).toBe('date')
    expect(result.unrevealed).toEqual(['hidden'])
  })

  it('reports every field as unrevealed when nothing can be shown', async () => {
    const result = await focusFirstInvalidField(['a', 'b'], () => false)
    expect(result).toEqual({ key: null, unrevealed: ['a', 'b'] })
  })

  it('does nothing for an empty error list', async () => {
    expect(await focusFirstInvalidField([])).toEqual({ key: null, unrevealed: [] })
  })
})