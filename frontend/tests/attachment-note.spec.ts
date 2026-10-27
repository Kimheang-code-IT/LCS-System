import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import km from '../i18n/locales/km.json'
import zh from '../i18n/locales/zh.json'
import { FILE_ATTACHMENT_COLUMNS } from '../app/config/freight-modules'

describe('attachment file table', () => {
  it('shows file name, note, by and created before the row actions', () => {
    // `#` and the actions menu are added by the shared renderer.
    expect(FILE_ATTACHMENT_COLUMNS.map(column => column.key)).toEqual([
      'fileName',
      'note',
      'uploadedBy',
      'uploadedAt',
    ])
  })

  it('edits the note in its own cell', () => {
    const note = FILE_ATTACHMENT_COLUMNS.find(column => column.key === 'note')!
    expect(note.computed).toBeFalsy()
    expect(note.rule?.maxLength).toBe(1000)
  })

  it('has the note column label in every locale', () => {
    for (const bundle of [en, km, zh]) {
      expect(bundle.freight.ui.cols.note).toBeTruthy()
    }
  })
})
