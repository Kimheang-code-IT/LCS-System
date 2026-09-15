import { describe, expect, it } from 'vitest'
import {
  componentInstanceLimits,
  componentSummaryAttributes,
  normalizeComponentAssignmentRecord,
  normalizeComponentInstanceMode,
  resolveComponentInstanceMode,
} from '../app/utils/freight/component-instance-mode'

describe('dynamic component instance mode', () => {
  it('uses assignment override before the template default', () => {
    expect(resolveComponentInstanceMode(
      { instanceModeOverride: 'INHERIT' },
      { instanceMode: 'REPEATABLE' },
    )).toBe('REPEATABLE')
    expect(resolveComponentInstanceMode(
      { instanceModeOverride: 'SINGLE' },
      { instanceMode: 'REPEATABLE' },
    )).toBe('SINGLE')
    expect(resolveComponentInstanceMode(
      { instanceModeOverride: 'REPEATABLE' },
      { instanceMode: 'SINGLE' },
    )).toBe('REPEATABLE')
  })

  it('normalizes legacy flags and defaults safely to single', () => {
    expect(normalizeComponentInstanceMode(undefined, 'Yes')).toBe('REPEATABLE')
    expect(normalizeComponentInstanceMode(undefined, true)).toBe('REPEATABLE')
    expect(normalizeComponentInstanceMode(undefined, 'No')).toBe('SINGLE')
    expect(normalizeComponentInstanceMode(undefined)).toBe('SINGLE')
    expect(normalizeComponentAssignmentRecord({ repeatable: 'No' }).instanceModeOverride).toBe('INHERIT')
    expect(normalizeComponentAssignmentRecord({ repeatable: 'Yes' }).instanceModeOverride).toBe('REPEATABLE')
  })

  it('does not confuse attribute multiple values with component cardinality', () => {
    expect(resolveComponentInstanceMode(null, {
      instanceMode: 'SINGLE',
      attributes: [{ code: 'tags', repeatable: 'Yes' }],
    })).toBe('SINGLE')
  })

  it('derives limits and generic summary fields', () => {
    expect(componentInstanceLimits({ required: 'Yes' }, { instanceMode: 'REPEATABLE' })).toEqual({
      minimum: 1,
      maximum: undefined,
    })
    expect(componentInstanceLimits(null, { minimumInstances: 2, maximumInstances: 4 })).toEqual({
      minimum: 2,
      maximum: 4,
    })
    expect(componentSummaryAttributes({ attributes: [
      { code: 'third', displayOrder: 30 },
      { code: 'first', displayOrder: 10, showInSummary: 'Yes' },
      { code: 'second', displayOrder: 20, showInSummary: 'Yes' },
    ] }).map(row => row.code)).toEqual(['first', 'second'])
  })

  it('resolves repeatable mode for all document component templates', () => {
    const repeatableTemplates = [
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
      { instanceMode: 'REPEATABLE', repeatable: 'Yes' },
    ]
    for (const template of repeatableTemplates) {
      expect(resolveComponentInstanceMode({ instanceModeOverride: 'INHERIT' }, template)).toBe('REPEATABLE')
    }
  })

  it('uses showInSummary fields for packing list and transport list columns', () => {
    expect(componentSummaryAttributes({ attributes: [
      { code: 'packing_list_no', displayOrder: 10, showInSummary: 'Yes' },
      { code: 'packages', displayOrder: 20, showInSummary: 'Yes' },
      { code: 'gross_weight', displayOrder: 30 },
    ] }).map(row => row.code)).toEqual(['packing_list_no', 'packages'])
    expect(componentSummaryAttributes({ attributes: [
      { code: 'truck_plate', displayOrder: 10, showInSummary: 'Yes' },
      { code: 'driver_name', displayOrder: 20, showInSummary: 'Yes' },
      { code: 'driver_phone', displayOrder: 30 },
    ] }).map(row => row.code)).toEqual(['truck_plate', 'driver_name'])
  })
})
