import { describe, expect, it } from 'vitest'
import {
  isDocumentOverflowAction,
  splitDocumentHeaderActions,
} from '~/utils/layout/document-header-actions'

describe('document header actions', () => {
  it('routes secondary actions to the overflow menu', () => {
    expect(isDocumentOverflowAction('print')).toBe(true)
    expect(isDocumentOverflowAction('reverse')).toBe(true)
    expect(isDocumentOverflowAction('post')).toBe(false)
    expect(isDocumentOverflowAction('saveDraft')).toBe(false)
  })

  it('splits workflow and menu actions', () => {
    const actions = [
      { key: 'post', label: 'Post' },
      { key: 'reverse', label: 'Reverse' },
      { key: 'print', label: 'Print' },
    ]
    expect(splitDocumentHeaderActions(actions)).toEqual({
      primary: [{ key: 'post', label: 'Post' }],
      overflow: [
        { key: 'reverse', label: 'Reverse' },
        { key: 'print', label: 'Print' },
      ],
    })
  })
})
