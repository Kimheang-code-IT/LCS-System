import { describe, expect, it } from 'vitest'
import { defaultUserAvatarUrl, resolveUserAvatar } from '../app/utils/auth/user-avatar'

describe('default user avatar', () => {
  it('inlines an SVG data URI instead of calling an external service', () => {
    const url = defaultUserAvatarUrl('E2E Tester')
    expect(url.startsWith('data:image/svg+xml;charset=utf-8,')).toBe(true)
    expect(url).not.toMatch(/^https?:/)
    expect(decodeURIComponent(url)).toContain('>ET<')
  })

  it('is deterministic per name and varies between names', () => {
    expect(defaultUserAvatarUrl('Moeng Kimheang')).toBe(defaultUserAvatarUrl('Moeng Kimheang'))
    expect(defaultUserAvatarUrl('Moeng Kimheang')).not.toBe(defaultUserAvatarUrl('Admin'))
  })

  it('escapes characters that would break the SVG', () => {
    expect(decodeURIComponent(defaultUserAvatarUrl('& <Admin>'))).toContain('&#38;')
  })

  it('prefers an uploaded avatar over the generated one', () => {
    expect(resolveUserAvatar({ name: 'A', avatar: 'https://cdn.example/a.png' }))
      .toBe('https://cdn.example/a.png')
    expect(resolveUserAvatar({ name: 'A' })).toMatch(/^data:image\/svg\+xml/)
    expect(resolveUserAvatar(null)).toMatch(/^data:image\/svg\+xml/)
  })
})
