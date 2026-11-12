import { describe, expect, it } from 'vitest'
import { serviceOrderStatusLabel } from '../app/utils/freight/states'

describe('service order status label', () => {
  it('presents a working ACTIVE order as Draft without changing the stored value', () => {
    expect(serviceOrderStatusLabel('ACTIVE')).toBe('Draft')
    expect(serviceOrderStatusLabel('active')).toBe('Draft')
    expect(serviceOrderStatusLabel('FINISHED')).toBe('FINISHED')
    expect(serviceOrderStatusLabel('INACTIVE')).toBe('INACTIVE')
    expect(serviceOrderStatusLabel('')).toBe('')
  })
})
