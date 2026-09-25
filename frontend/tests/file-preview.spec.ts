import { describe, expect, it } from 'vitest'
import { filePreviewHref, mimeFromFileName } from '../app/utils/freight/attachments'
import { safeExternalUrl, safeFilePreviewUrl } from '../app/utils/security/url'

describe('file preview', () => {
  it('maps common extensions to preview mime types', () => {
    expect(mimeFromFileName('BL-8821.pdf')).toBe('application/pdf')
    expect(mimeFromFileName('scan.PNG')).toBe('image/png')
    expect(mimeFromFileName('notes.txt')).toBe('text/plain')
    expect(mimeFromFileName('photo.jpg', 'image/jpeg')).toBe('image/jpeg')
  })

  it('never fabricates a preview for rows without real content', () => {
    expect(filePreviewHref({ fileName: 'BL-8821.pdf' })).toBeNull()
    expect(filePreviewHref({ fileName: 'gate-photo.png' })).toBeNull()
  })

  it('returns the persisted http(s) URL when one exists', () => {
    expect(filePreviewHref({ fileName: 'BL-8821.pdf', url: 'https://files.example.com/bl.pdf' }))
      .toBe('https://files.example.com/bl.pdf')
  })

  it('rejects executable URL schemes and keeps http(s) plus blob', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(safeFilePreviewUrl('javascript:alert(1)')).toBeNull()
    expect(safeFilePreviewUrl('https://files.example.com/bl.pdf')).toBe('https://files.example.com/bl.pdf')
    expect(safeFilePreviewUrl('blob:https://localhost/1234')).toBe('blob:https://localhost/1234')
  })
})
