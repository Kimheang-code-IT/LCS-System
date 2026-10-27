/**
 * Container Types is a metadata-driven Master Data module: the form, the list and
 * the API spec are generated from this config, so a missing field or rule fails
 * silently (an unrendered input) rather than with an error. These tests pin the
 * full field set, the required/unique code, decimal dimensions, and the shared
 * number input actually keeping decimals instead of snapping them.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const containerTypes = getFreightModule('/master-data/container-types')!
const byKey = Object.fromEntries(containerTypes.fields.map(field => [field.key, field]))

describe('container types module', () => {
  it('is a standard, creatable master-data module', () => {
    expect(containerTypes.collection).toBe('containerTypes')
    expect(containerTypes.kind).toBe('standard')
    expect(containerTypes.canCreate).toBe(true)
  })

  it('offers every container field the owner listed', () => {
    expect(containerTypes.fields.map(field => field.key)).toEqual(
      expect.arrayContaining([
        'code',
        'name',
        'size',
        'kind',
        'isoCode',
        'lengthFeet',
        'widthMeters',
        'heightMeters',
        'maxGrossWeightKg',
      ]),
    )
  })

  it('requires code and name so a blank record cannot be saved', () => {
    expect(byKey.code!.required).toBe(true)
    expect(byKey.name!.required).toBe(true)
    expect(byKey.code!.rule?.maxLength).toBe(50)
  })

  it('accepts any non-negative number for the dimension fields', () => {
    for (const key of ['lengthFeet', 'widthMeters', 'heightMeters', 'maxGrossWeightKg']) {
      expect(byKey[key]!.type, key).toBe('number')
      expect(byKey[key]!.rule, key).toMatchObject({ number: true, nonNegative: true })
      // No `integer` rule: a width like 2.438 must be allowed.
      expect(byKey[key]!.rule?.integer, key).toBeFalsy()
    }
  })

  it('shows the compact list columns, keeping dimensions in the detail form', () => {
    const columns = containerTypes.columns.map(column => column.key)
    expect(columns).toEqual([
      'code',
      'name',
      'size',
      'isoCode',
      'maxGrossWeightKg',
      'status',
      'createdBy',
      'createdAt',
    ])
    // Width/height remain editable on the record even though the list is compact.
    expect(byKey.widthMeters).toBeDefined()
    expect(byKey.heightMeters).toBeDefined()
  })
})

describe('decimal number inputs', () => {
  it('do not snap a typed decimal to the whole-number step', () => {
    // reka-ui's NumberField snaps to `step` (default 1) unless step-snapping is
    // switched off, which turned 2.438 into 2 and 2.591 into 3 on blur.
    //
    // The Container Types form renders through AppDynamicFieldRenderer, NOT
    // AppFieldGrid — patching only the latter left the bug live. Every number
    // input is pinned here so the same mistake cannot recur.
    const cases: Array<[string, string]> = [
      ['components/document/AppDynamicFieldRenderer.vue', ':step-snapping="false"'],
      ['components/document/AppFieldGrid.vue', ':step-snapping="false"'],
      ['components/document/DynamicFormRenderer.vue', ':step-snapping="false"'],
      ['components/freight/JobContainers.vue', ':step-snapping="false"'],
      ['components/freight/AppLineTable.vue', "'stepSnapping': false"],
    ]
    for (const [file, expected] of cases) {
      const source = readFileSync(`${APP}/${file}`, 'utf8')
      expect(source, file).toContain(expected)
    }
  })
})
