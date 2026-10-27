import { describe, expect, it } from 'vitest'
import { documentActionButtonUi } from '~/utils/layout/document-action-button'

describe('documentActionButtonUi', () => {
  it('matches the list header create button: neutral solid', () => {
    expect(documentActionButtonUi()).toEqual({ color: 'neutral', variant: 'solid' })
    expect(documentActionButtonUi('primary')).toEqual({ color: 'neutral', variant: 'solid' })
    expect(documentActionButtonUi('success')).toEqual({ color: 'neutral', variant: 'solid' })
    expect(documentActionButtonUi('warning')).toEqual({ color: 'neutral', variant: 'solid' })
  })
})
