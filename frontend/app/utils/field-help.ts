type Translate = (key: string, values?: Record<string, unknown>) => string
type TranslateExists = (key: string) => boolean

export type FormFieldHelpSource = {
  key: string
  label?: string
  help?: string
  helpKey?: string
  computed?: boolean
}

function firstExistingHelp(t: Translate, te: TranslateExists, keys: string[]): string | undefined {
  for (const key of keys) {
    if (key && te(key)) return t(key)
  }
}

/**
 * ERPNext-style helper text under every form field.
 * Order: literal help → helpKey → freight.fieldHelp → docetra.fieldHelp → calculated → default.
 */
export function resolveFormFieldHelp(
  field: FormFieldHelpSource,
  t: Translate,
  te: TranslateExists,
): string {
  const literal = String(field.help || '').trim()
  if (literal) return literal
  if (field.helpKey && te(field.helpKey)) return t(field.helpKey)

  const key = String(field.key || '').trim()
  const leaf = key.includes('.') ? key.slice(key.lastIndexOf('.') + 1) : key
  const found = firstExistingHelp(t, te, [
    `freight.fieldHelp.${key}`,
    `docetra.fieldHelp.${key}`,
    `freight.fieldHelp.${leaf}`,
    `docetra.fieldHelp.${leaf}`,
  ])
  if (found) return found

  if (field.computed && te('freight.ui.calculatedHelp')) {
    return t('freight.ui.calculatedHelp')
  }

  const label = String(field.label || leaf || key || '').trim()
  if (te('docetra.fieldHelp.default')) return t('docetra.fieldHelp.default', { field: label })
  return t('freight.ui.enterFieldHelp', { field: label })
}

/**
 * Resolve ERPNext-style helper text for a document field schema.
 */
export function resolveFieldHelp(
  field: Pick<FormFieldHelpSource, 'key' | 'helpKey' | 'help' | 'computed'> & { labelKey?: string },
  label: string,
  t: Translate,
  te: TranslateExists,
): string {
  return resolveFormFieldHelp({ ...field, label }, t, te)
}
