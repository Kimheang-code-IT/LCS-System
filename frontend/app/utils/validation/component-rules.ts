/**
 * Validation rules for the database-driven Service Order tabs.
 *
 * Component attributes ship their constraints as a free-form admin-managed
 * JSON blob (`validation_rules`), so this module translates the conventional
 * key names an administrator is likely to use into the shared {@link FieldRule}
 * shape. Unknown keys are ignored rather than rejected, so a configuration
 * written before this feature existed keeps working.
 *
 * Rules are read from the *published* configuration snapshot the order is
 * pinned to, which is what `useComponentTabs` loads — so a historical order is
 * validated exactly as it was captured.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

import type { ComponentTabAttribute, ComponentTabGroup } from '~/types/component-config'
import type { FieldRule, ValidationFailure } from './field-rules'
import { validateFieldValue } from './field-rules'

/** Accepted spellings for each rule, so admin JSON does not have to be exact. */
const RULE_ALIASES = {
  min: ['min', 'minValue', 'minimum'],
  max: ['max', 'maxValue', 'maximum'],
  minLength: ['minLength', 'min_length', 'minChars'],
  maxLength: ['maxLength', 'max_length', 'maxChars'],
  pattern: ['pattern', 'regex'],
  allowed: ['allowed', 'allowedValues', 'allowed_values', 'enum', 'options'],
} as const

function firstNumber(rules: Record<string, unknown>, keys: readonly string[]): number | undefined {
  for (const key of keys) {
    const value = rules[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  }
  return undefined
}

function firstString(rules: Record<string, unknown>, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = rules[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return undefined
}

function firstList(rules: Record<string, unknown>, keys: readonly string[]): string[] | undefined {
  for (const key of keys) {
    const value = rules[key]
    if (Array.isArray(value) && value.length) return value.map(item => String(item))
  }
  return undefined
}

function firstBoolean(rules: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.some(key => rules[key] === true)
}

/**
 * Merge the attribute's own flags with its admin-managed `validationRules`.
 * Type inference mirrors {@link inferFieldRule}: dates must parse, numbers must
 * be finite, an attribute named `*email` must be an email.
 */
export function componentAttributeRule(attribute: ComponentTabAttribute): FieldRule {
  const raw = (attribute.validationRules || {}) as Record<string, unknown>
  const rule: FieldRule = { required: Boolean(attribute.isRequired) || firstBoolean(raw, ['required', 'isRequired']) }

  switch (attribute.fieldType) {
    case 'integer':
      rule.integer = true
      break
    case 'number':
    case 'decimal':
    case 'money':
      rule.integer = attribute.fieldType === 'number' || firstBoolean(raw, ['integer', 'wholeNumber'])
      break
    case 'date':
    case 'datetime':
      rule.date = true
      break
    default:
      break
  }
  if (/e?mail$/i.test(attribute.code)) rule.email = true
  if (firstBoolean(raw, ['email'])) rule.email = true
  if (firstBoolean(raw, ['url'])) rule.url = true
  if (firstBoolean(raw, ['nonNegative', 'non_negative'])) rule.nonNegative = true
  if (firstBoolean(raw, ['positive'])) {
    rule.nonNegative = true
    rule.min = 1
  }

  const min = firstNumber(raw, RULE_ALIASES.min)
  const max = firstNumber(raw, RULE_ALIASES.max)
  if (min !== undefined) rule.min = min
  if (max !== undefined) rule.max = max

  const minLength = firstNumber(raw, RULE_ALIASES.minLength)
  const maxLength = firstNumber(raw, RULE_ALIASES.maxLength)
  if (minLength !== undefined) rule.minLength = minLength
  if (maxLength !== undefined) rule.maxLength = maxLength

  const pattern = firstString(raw, RULE_ALIASES.pattern)
  if (pattern) rule.pattern = pattern

  const allowed = firstList(raw, RULE_ALIASES.allowed) ?? firstList(raw, ['allowedValues'])
  if (allowed?.length) rule.allowed = allowed

  // A select whose configured options define the closed set.
  const options = Array.isArray(attribute.options) ? attribute.options : []
  if (options.length && !rule.allowed) {
    rule.allowed = options.map(option => (typeof option === 'string' ? option : option.value))
  }

  return rule
}

/**
 * Canonical key for a value inside a dynamic component group.
 * Group ids are globally unique, so `groupId.rowIndex.code` is stable and
 * unambiguous across tabs.
 */
export function componentCellKey(groupId: string, rowIndex: number, code: string): string {
  return `${groupId}.${rowIndex}.${code}`
}

export type ComponentValidationInput = {
  group: Pick<ComponentTabGroup, 'id' | 'attributes'>
  rows: ReadonlyArray<Record<string, unknown>>
  label: (attribute: ComponentTabAttribute) => string
  /** Rows created in the browser may legitimately still be empty while editing. */
  skipBlankRows?: boolean
}

/**
 * Validate one component group's rows (table mode uses one row per line,
 * form mode always uses row 0).
 */
export function validateComponentRows(input: ComponentValidationInput): ValidationFailure[] {
  const { group, rows, label, skipBlankRows } = input
  const attributes = [...group.attributes].sort((a, b) => a.sortOrder - b.sortOrder)
  const failures: ValidationFailure[] = []

  rows.forEach((row, index) => {
    if (skipBlankRows && isBlankRow(row, attributes)) return
    for (const attribute of attributes) {
      const issue = validateFieldValue(row[attribute.code], componentAttributeRule(attribute))
      if (!issue) continue
      failures.push({
        ...issue,
        key: componentCellKey(group.id, index, attribute.code),
        row: index,
        label: label(attribute),
      })
    }
  })

  return failures
}

/** A row the user added but never filled in is not an error until it is used. */
function isBlankRow(row: Record<string, unknown>, attributes: readonly ComponentTabAttribute[]): boolean {
  return attributes.every(attribute => {
    const value = row[attribute.code]
    if (attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean') return false
    if (Array.isArray(value)) return value.length === 0
    return String(value ?? '').trim() === ''
  })
}