import { describe, expect, it } from 'vitest'
import { tableRowCommentCount, tableRowInitials, tableRowStamp } from '../app/utils/table/row-meta'

describe('table row meta', () => {
  it('prefers updatedAt for the stamp', () => {
    expect(tableRowStamp({ updatedAt: '2026-08-20T10:00:00', createdAt: '2026-08-01T08:00:00' }))
      .toBe('2026-08-20T10:00:00')
  })

  it('counts comments on the record', () => {
    expect(tableRowCommentCount({ comments: [{ id: 'c1' }, { id: 'c2' }] })).toBe(2)
    expect(tableRowCommentCount({ commentCount: 4 })).toBe(4)
    expect(tableRowCommentCount({})).toBe(0)
  })

  it('builds initials from the assigned staff name', () => {
    expect(tableRowInitials({ assignedStaff: 'Sophea Chan' })).toBe('SC')
    expect(tableRowInitials({ assignedStaff: 'Sophea' })).toBe('S')
    expect(tableRowInitials({})).toBe('S')
  })
})
