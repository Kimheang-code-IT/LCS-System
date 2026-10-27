/**
 * Inline editing rules for the Component Attributes grid.
 *
 * The page owns the row set and the API calls; this leaf module owns the
 * decisions that are easy to get wrong and worth testing without a browser:
 * which value belongs to which column, when a value actually changed, which
 * validation rule applies, and how a backend field error lands on a cell.
 *
 * Keep it a leaf: no Vue, no components, no i18n.
 */

import type { ComponentAttributeInput } from '~/types/component-config'
import { COMPONENT_DATA_TYPES } from '~/types/component-config'
import type { ValidationIssue } from '~/utils/validation/field-rules'
import { validateFieldValue } from '~/utils/validation/field-rules'
import { normalizeApiError } from '~/utils/validation/api-error'
import { rowCellKey } from '~/utils/validation/error-paths'
import {
  componentAttributeDataType,
  componentReferenceType,
  mergeAttributeRules,
  normalizeAttributeCode,
  parseAttributeOptions,
  parseAttributeRules,
} from '~/utils/freight/component-config-tables'

export const ATTRIBUTE_TABLE_KEY = 'componentAttributes'
export const ATTRIBUTE_CODE_MAX_LENGTH = 64
export const ATTRIBUTE_LABEL_MAX_LENGTH = 255
export const ATTRIBUTE_HELP_MAX_LENGTH = 255
export const ATTRIBUTE_OPTIONS_MAX_LENGTH = 1000
export const ATTRIBUTE_RULES_MAX_LENGTH = 500

export type AttributeFieldKey =
  | 'code'
  | 'label'
  | 'dataType'
  | 'options'
  | 'referenceType'
  | 'validationRules'
  | 'isRequired'
  | 'helpText'
export type AttributeRow = Record<string, unknown>

const ATTRIBUTE_FIELDS: AttributeFieldKey[] = [
  'code',
  'label',
  'dataType',
  'options',
  'referenceType',
  'validationRules',
  'isRequired',
  'helpText',
]

export function isAttributeFieldKey(value: unknown): value is AttributeFieldKey {
  return typeof value === 'string' && (ATTRIBUTE_FIELDS as string[]).includes(value)
}

export function attributeCellKey(index: number, key: AttributeFieldKey): string {
  return rowCellKey(ATTRIBUTE_TABLE_KEY, index, key)
}

function text(value: unknown): string {
  return String(value ?? '').trim()
}

/** The value the grid shows for one editable column. */
export function attributeFieldValue(key: AttributeFieldKey, row: AttributeRow): string | boolean {
  switch (key) {
    case 'isRequired':
      return Boolean(row.isRequired)
    case 'dataType':
      return componentAttributeDataType(row.dataType)
    case 'referenceType':
      return componentReferenceType(row.referenceType) || ''
    case 'code':
      return text(row.code)
    case 'options':
      return text(row.options)
    case 'validationRules':
      return text(row.validationRules)
    case 'helpText':
      return text(row.helpText)
    default:
      return text(row.label)
  }
}

/**
 * Whether a cell still matches the last value the server confirmed. Text is
 * compared trimmed, so adding and removing a trailing space is not a request.
 */
export function sameAttributeFieldValue(
  key: AttributeFieldKey,
  left: unknown,
  right: unknown,
): boolean {
  if (key === 'isRequired') return Boolean(left) === Boolean(right)
  return text(left) === text(right)
}

/**
 * The partial body a PATCH sends. One field only: editing Help Text must never
 * carry a stale Label value over a newer Label edit.
 */
export function attributeFieldPayload(key: AttributeFieldKey, row: AttributeRow): ComponentAttributeInput {
  switch (key) {
    case 'isRequired':
      return { isRequired: Boolean(row.isRequired) }
    case 'dataType':
      return { dataType: componentAttributeDataType(row.dataType) }
    case 'code':
      return { code: text(row.code) }
    case 'options':
      return { options: parseAttributeOptions(row.options) }
    case 'referenceType':
      return { referenceType: componentReferenceType(row.referenceType) }
    case 'validationRules':
      return { validationRules: mergeAttributeRules(row.validationRules, row.validationRuleExtras) }
    case 'helpText':
      return { placeholder: text(row.helpText) }
    default:
      return { label: text(row.label) }
  }
}

/** Client-side rule for one cell. `isRequired` is a checkbox, never invalid. */
export function attributeFieldIssue(
  key: AttributeFieldKey,
  row: AttributeRow,
  takenCodes: readonly string[] = [],
): ValidationIssue | null {
  switch (key) {
    case 'code': {
      const code = text(row.code)
      const issue = validateFieldValue(code, {
        required: true,
        maxLength: ATTRIBUTE_CODE_MAX_LENGTH,
        pattern: '^[a-zA-Z0-9][a-zA-Z0-9_-]*$',
      })
      if (issue) return issue
      if (takenCodes.some(taken => normalizeAttributeCode(taken) === normalizeAttributeCode(code))) {
        return { code: 'custom', message: 'This code is already used by another attribute.' }
      }
      return null
    }
    case 'label':
      return validateFieldValue(row.label, {
        required: true,
        maxLength: ATTRIBUTE_LABEL_MAX_LENGTH,
      })
    case 'helpText':
      return validateFieldValue(row.helpText, { maxLength: ATTRIBUTE_HELP_MAX_LENGTH })
    case 'dataType':
      return validateFieldValue(componentAttributeDataType(row.dataType), {
        required: true,
        allowed: COMPONENT_DATA_TYPES,
      })
    case 'options': {
      const issue = validateFieldValue(row.options, { maxLength: ATTRIBUTE_OPTIONS_MAX_LENGTH })
      if (issue) return issue
      const dataType = componentAttributeDataType(row.dataType)
      if (
        (dataType === 'select' || dataType === 'multi_select')
        && parseAttributeOptions(row.options).length === 0
      ) {
        return { code: 'required' }
      }
      return null
    }
    case 'referenceType':
      if (componentAttributeDataType(row.dataType) !== 'reference') return null
      if (!componentReferenceType(row.referenceType)) return { code: 'required' }
      return null
    case 'validationRules': {
      const issue = validateFieldValue(row.validationRules, { maxLength: ATTRIBUTE_RULES_MAX_LENGTH })
      if (issue) return issue
      const parsed = parseAttributeRules(row.validationRules)
      return parsed.error ? { code: 'custom', message: parsed.error } : null
    }
    default:
      return null
  }
}

/**
 * Map a backend refusal onto the cell that caused it.
 *
 * The API speaks the persisted field names (`code`, `placeholder`, snake_case),
 * while the grid edits `label` and `helpText`.
 */
const SERVER_FIELD_ALIASES: Record<string, AttributeFieldKey> = {
  label: 'label',
  code: 'code',
  dataType: 'dataType',
  data_type: 'dataType',
  isRequired: 'isRequired',
  is_required: 'isRequired',
  helpText: 'helpText',
  placeholder: 'helpText',
  options: 'options',
  referenceType: 'referenceType',
  reference_type: 'referenceType',
  validationRules: 'validationRules',
  validation_rules: 'validationRules',
}

export type AttributeServerError = {
  /** Ready-to-render cell messages keyed `componentAttributes.<index>.<column>`. */
  fieldErrors: Record<string, string>
  /** Messages no cell can take (business rule, transport failure). */
  message: string
  /** 400/409/422 — the request was understood and rejected. */
  isValidation: boolean
}

export function attributeServerError(error: unknown, index: number): AttributeServerError {
  const normalized = normalizeApiError(error)
  const fieldErrors: Record<string, string> = {}
  const formLevel: string[] = []

  for (const item of normalized.items) {
    const target = SERVER_FIELD_ALIASES[item.key]
    if (!target) {
      if (item.message) formLevel.push(item.message)
      continue
    }
    const key = attributeCellKey(index, target)
    if (!(key in fieldErrors)) fieldErrors[key] = item.message
  }

  if (normalized.message) formLevel.push(normalized.message)

  return {
    fieldErrors,
    message: formLevel.join(' '),
    isValidation: normalized.isValidation,
  }
}
