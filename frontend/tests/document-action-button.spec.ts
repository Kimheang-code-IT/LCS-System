import { describe, expect, it } from 'vitest'
import { documentActionButtonUi } from '~/utils/layout/document-action-button'

describe('documentActionButtonUi', () => {
  it('uses outline neutral for secondary actions', () => {
    expect(documentActionButtonUi()).toEqual({ color: 'neutral', variant: 'outline' })
    expect(documentActionButtonUi('warning')).toEqual({ color: 'neutral', variant: 'outline' })
  })

  it('uses solid for primary CTAs', () => {
    expect(documentActionButtonUi('primary')).toEqual({ color: 'primary', variant: 'solid' })
    expect(documentActionButtonUi('success')).toEqual({ color: 'success', variant: 'solid' })
  })
})
