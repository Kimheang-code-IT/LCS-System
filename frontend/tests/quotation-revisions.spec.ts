import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import { getFreightModule } from '../app/config/freight-modules'
import {
  formatRevisionNo,
  revisionGridRows,
} from '../app/utils/freight/quotation-revisions'

const revisionTable = getFreightModule('/quotations')!.tables!.find(table => table.key === 'revisionHistory')!

describe('quotation list columns', () => {
  it('shows the seven business columns in order', () => {
    expect(getFreightModule('/quotations')!.columns.map(column => column.key)).toEqual([
      'quotationNo',
      'serviceOrderNo',
      'customer',
      'revisionNo',
      'direction',
      'total',
      'status',
      'createdBy',
      'createdAt',
    ])
  })

  it('labels the party column and filter as Business Party', () => {
    const quotation = getFreightModule('/quotations')!
    const column = quotation.columns.find(item => item.key === 'customer')
    const filter = quotation.filters?.find(item => item.key === 'customer')
    expect(column?.label).toBe('Business Party')
    expect(column?.labelKey).toBe('freight.fields.customerPartyId')
    expect(filter?.label).toBe('Business Party')
    expect(filter?.labelKey).toBe('freight.fields.customerPartyId')
    expect(en.freight.fields.customerPartyId).toBe('Business Party')
  })

  it('formats revision numbers as R01 and never as a decimal', () => {
    expect(formatRevisionNo(1)).toBe('R01')
    expect(formatRevisionNo(2)).toBe('R02')
    expect(formatRevisionNo(12)).toBe('R12')
    expect(formatRevisionNo(2.0)).toBe('R02')
    expect(formatRevisionNo(null)).toBe('—')
  })
})

describe('quotation revision history', () => {
  it('shows revision, status, grand total, creator and creation time', () => {
    expect(revisionTable.columns.map(column => column.key)).toEqual([
      'revisionNo',
      'status',
      'total',
      'createdBy',
      'createdAt',
    ])
    expect(revisionTable.columns.find(column => column.key === 'total')?.computed).toBe(true)
    // Revision is a short number column; the trailing actions menu is renderer-added.
    expect(revisionTable.columns.find(column => column.key === 'revisionNo')?.width).toBe(72)
  })

  it('sorts newest first, formats R01 numbers and shows an em dash for an unknown creator', () => {
    const rows = revisionGridRows([
      { id: '1', revisionNo: 1, createdBy: 'Sokha' },
      { id: '2', revisionNo: 2, createdBy: 42 },
    ])
    expect(rows.map(row => row.revisionNo)).toEqual(['R02', 'R01'])
    expect(rows[0]?.createdBy).toBe('—')
    expect(rows[1]?.createdBy).toBe('Sokha')
  })
})
