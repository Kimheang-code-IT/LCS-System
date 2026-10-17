import { describe, expect, it } from 'vitest'
import {
  camelizeKey,
  fromErrorPath,
  matchesRegisteredKey,
  normalizeErrorKey,
  parseRowKey,
  referencedTables,
  rowCellKey,
  toErrorPath,
} from '../app/utils/validation/error-paths'

describe('error paths', () => {
  it('camelizes snake_case backend keys onto camelCase model fields', () => {
    expect(camelizeKey('customer_party_id')).toBe('customerPartyId')
    expect(camelizeKey('valid_until')).toBe('validUntil')
    expect(camelizeKey('customer')).toBe('customer')
  })

  it('drops the FastAPI envelope segment', () => {
    expect(toErrorPath('body.customer_party_id')).toEqual(['customerPartyId'])
    expect(toErrorPath('query.page')).toEqual(['page'])
    expect(toErrorPath('')).toEqual([])
  })

  it('keeps array indices so nested errors reach the right row', () => {
    expect(toErrorPath('lines.1.amount')).toEqual(['lines', 1, 'amount'])
    expect(normalizeErrorKey('body.lines.2.unit_amount')).toBe('lines.2.unitAmount')
    expect(normalizeErrorKey('places.0.planned_date')).toBe('places.0.plannedDate')
  })

  it('round-trips a row cell key', () => {
    const key = rowCellKey('feeLines', 3, 'unitAmount')
    expect(key).toBe('feeLines.3.unitAmount')
    expect(parseRowKey(key)).toEqual({ table: 'feeLines', index: 3, column: 'unitAmount' })
    expect(fromErrorPath(toErrorPath(key))).toBe(key)
  })

  it('returns null for keys that address a whole table', () => {
    expect(parseRowKey('lines')).toBeNull()
    expect(parseRowKey('lines.amount')).toBeNull()
    expect(parseRowKey('lines.x.amount')).toBeNull()
  })

  it('resolves a row error back to the table field that owns it', () => {
    const registered = ['header', 'lines', 'allocations']
    expect(matchesRegisteredKey('lines.1.amount', registered)).toBe('lines')
    expect(matchesRegisteredKey('customerPartyId', registered)).toBeNull()
    // A prefix match must pick the longest registered key, not the first one.
    expect(matchesRegisteredKey('user.name', ['user', 'userProfile'])).toBe('user')
    expect(matchesRegisteredKey('userProfile.name', ['user', 'userProfile'])).toBe('userProfile')
  })

  it('does not collapse a cell error onto the whole table', () => {
    const registered = ['lines']
    // The owner is reported for the reveal step, but the exact cell key must
    // survive so the message lands on that input and not on the table header.
    expect(matchesRegisteredKey('lines.1.amount', registered)).toBe('lines')
    expect(matchesRegisteredKey('lines.amount', registered)).toBe('lines')
    expect(normalizeErrorKey('lines.1.amount')).toBe('lines.1.amount')
  })

  it('lists the repeatable tables referenced by a key set', () => {
    expect(referencedTables(['lines.1.amount', 'lines.2.amount', 'allocations'])).toEqual(['lines', 'allocations'])
  })
})