/**
 * Form-level validation for the config-driven document forms and their
 * repeatable tables.
 *
 * Everything is derived from the module config (`freight-modules.ts`) and the
 * dynamic component configuration, so a new module gets validation by being
 * declared, not by writing a bespoke rule object.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

import type { FreightField, FreightLineColumn, FreightTable } from '~/config/freight-modules'
import { rowCellKey } from './error-paths'
import type { FieldRule, ValidationFailure } from './field-rules'
import { validateFieldValue } from './field-rules'

/** Field keys that look like an email even when the column type is plain text. */
function infersEmail(key: string): boolean {
  return /(^|[a-z])e?mail$/i.test(key) || /email$/i.test(key)
}

/**
 * Field keys that carry a telephone number even when the column type is plain
 * text. Matching is per camelCase/underscore token rather than on the raw suffix,
 * so `phone`, `contactPhone` and `phoneNumber` qualify while `hotel` does not.
 */
function infersPhone(key: string): boolean {
  const tokens = String(key).replace(/([a-z0-9])([A-Z])/g, '$1 $2').split(/[^A-Za-z0-9]+/)
  return tokens.some(token => /^(phone|telephone|mobile|fax|contactnumber|phonenumber)$/i.test(token))
}

function infersUrl(fieldType?: string): boolean {
  return fieldType === 'url'
}

export type FieldRuleInput = Pick<FreightField, 'key' | 'type' | 'required' | 'computed' | 'createOnly' | 'rule' | 'options'>

/** First value of each declared option, normalised to a string. */
function optionValues(options: FreightField['options']): string[] | undefined {
  if (!options?.length) return undefined
  const values = options
    .map(option => (option && typeof option === 'object' && 'value' in option ? String(option.value) : String(option)))
    .map(value => value.trim())
    .filter(Boolean)
  return values.length ? values : undefined
}

/** Base rule inferred from the field's own metadata. */
export function inferFieldRule(field: FieldRuleInput): FieldRule {
  const rule: FieldRule = { required: Boolean(field.required) }
  if (infersEmail(field.key)) rule.email = true
  if (infersPhone(field.key)) rule.phone = true
  if (infersUrl(field.type)) rule.url = true
  // Any password the backend will hash has to satisfy the shared policy
  // (`validate_password_strength`); inferring it from the input type means a
  // new password form cannot silently skip the check.
  if (field.type === 'password' || field.key === 'password') rule.password = true
  if (field.type === 'date' || field.type === 'datetime') rule.date = true
  // A select can only hold one of its declared values; a reference select has
  // no static options, so its membership is the backend's call.
  if (field.type === 'select') rule.allowed = optionValues(field.options)
  return { ...rule, ...(field.rule || {}) }
}

/** Rule inferred from a line-table column definition. */
export function inferColumnRule(column: Pick<FreightLineColumn, 'key' | 'type' | 'required' | 'options' | 'rule'>): FieldRule {
  const rule: FieldRule = { required: Boolean(column.required) }
  // A number column must at least parse; `integer` narrows it further.
  if (column.type === 'number') rule.number = true
  if (column.type === 'date' || column.type === 'datetime') rule.date = true
  if (infersEmail(column.key)) rule.email = true
  if (infersPhone(column.key)) rule.phone = true
  if (column.options?.length) rule.allowed = [...column.options]
  return { ...rule, ...(column.rule || {}) }
}

export type DocumentValidationInput = {
  fields: readonly FieldRuleInput[]
  model: Record<string, unknown>
  /** Create-only fields (e.g. the initial password) are skipped when updating. */
  isCreate: boolean
  /** Keys that must not be validated in this context (e.g. read-only mirrors). */
  skipKeys?: readonly string[]
  /** Extra rules merged over the inferred ones (business-specific overrides). */
  rules?: Record<string, FieldRule>
  /** Resolves the display label; supplied by the caller so it can translate. */
  label: (key: string) => string
  /** Cross-field rules keyed by field; run after every field passes. */
  formRules?: Record<string, (model: Record<string, unknown>) => ValidationFailure | null>
}

export type TableValidationInput = {
  table: Pick<FreightTable, 'key' | 'columns'>
  rows: ReadonlyArray<Record<string, unknown>>
  label: (key: string) => string
  columnLabel?: (column: Pick<FreightLineColumn, 'key' | 'label'>) => string
  /** Reject a table with no rows at all (error keyed on the table field). */
  minRows?: number
  /**
   * Position of each row in the grid, aligned with `rows`. Pass this when only
   * a subset is validated, so `table.<index>.<column>` still addresses the row
   * the user sees rather than the row's place in the filtered array.
   */
  rowIndices?: readonly number[]
}

/**
 * Validate the scalar fields of a document.
 *
 * Computed/derived fields are skipped: the backend owns them and they are not
 * user-editable, so blocking on them would be noise.
 */
export function validateDocumentFields(input: DocumentValidationInput): ValidationFailure[] {
  const { fields, model, isCreate, skipKeys, rules, label, formRules } = input
  const skip = new Set(skipKeys ?? [])
  const failures: ValidationFailure[] = []

  for (const field of fields) {
    if (skip.has(field.key)) continue
    if (field.computed) continue
    if (field.createOnly && !isCreate) continue
    const rule = { ...inferFieldRule(field), ...(rules?.[field.key] || {}) }
    const issue = validateFieldValue(model[field.key], rule)
    if (issue) failures.push({ ...issue, key: field.key, label: label(field.key) })
  }

  for (const [key, check] of Object.entries(formRules || {})) {
    const issue = check(model)
    if (issue) failures.push({ ...issue, key, label: label(key) })
  }

  return failures
}

/**
 * Validate every cell of a repeatable table.
 *
 * Failures are keyed `table.<rowIndex>.<column>`, so a re-render, an add, a
 * remove or a reorder can never silently move an error onto another row: the
 * owning form clears row-scoped errors whenever the row set changes and
 * recomputes them on the next submit.
 */
export function validateTableRows(input: TableValidationInput): ValidationFailure[] {
  const { table, rows, label, columnLabel, minRows, rowIndices } = input
  const failures: ValidationFailure[] = []
  const columns = table.columns.filter(column =>
    column.type !== 'delete' && column.type !== 'action' && column.type !== 'reorder' && column.type !== 'note',
  )

  if (minRows !== undefined && rows.length < minRows) {
    failures.push({
      code: 'custom',
      key: table.key,
      label: label(table.key),
      message: 'minRows',
      params: { min: minRows },
    })
  }

  rows.forEach((row, position) => {
    const index = rowIndices?.[position] ?? position
    for (const column of columns) {
      const rule = inferColumnRule(column)
      // Columns marked `computed` are derived by the table, not typed by a user.
      if (column.computed && !column.required) continue
      const issue = validateFieldValue(row[column.key], rule)
      if (!issue) continue
      failures.push({
        ...issue,
        key: rowCellKey(table.key, index, column.key),
        row: index,
        label: columnLabel?.(column) || column.label || column.key,
      })
    }
    // Inline cells (discount / tax beside a computed total) are editable inputs
    // of their own, so a bad value must address its exact sub-cell rather than
    // the computed column that owns the layout.
    for (const column of columns) {
      for (const inline of column.inlineFields || []) {
        const rule = inferColumnRule({
          key: inline.key,
          type: 'number',
          required: Boolean(inline.required),
          rule: inline.rule,
        })
        const issue = validateFieldValue(row[inline.key], rule)
        if (!issue) continue
        failures.push({
          ...issue,
          key: rowCellKey(table.key, index, inline.key),
          row: index,
          label: columnLabel?.(inline as FreightLineColumn) || inline.label || inline.key,
        })
      }
    }
  })

  return failures
}

/**
 * Validate a flat draft object (dialog forms, settings panels).
 *
 * A convenience wrapper for the common "a handful of plain inputs" case, so
 * those screens share the same rules and the same inline rendering as the
 * document forms instead of re-implementing both.
 */
export function validateDraftFields(
  draft: Record<string, unknown>,
  fields: Array<Pick<FreightField, 'key' | 'required' | 'type' | 'rule'>>,
  label: (key: string) => string,
): ValidationFailure[] {
  return validateDocumentFields({ fields, model: draft, isCreate: true, label })
}

/** Collapse failures into the `fieldErrors` map the shared renderer reads. */
export function failuresToMap(
  failures: readonly ValidationFailure[],
  message: (failure: ValidationFailure) => string,
): Record<string, string> {
  const map: Record<string, string> = {}
  for (const failure of failures) {
    if (!failure.key) continue
    // First failure wins so the summary and the field always agree.
    if (!(failure.key in map)) map[failure.key] = message(failure)
  }
  return map
}