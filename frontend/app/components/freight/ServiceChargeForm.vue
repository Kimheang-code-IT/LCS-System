<script setup lang="ts">
/**
 * The Service Charge form, shared by the standalone `/service-charges` page
 * (inside `DocumentView`) and the Service Order's Service Charge tab.
 *
 * It owns no chrome and no publication: it renders the `jobCharges` module's
 * tabs through the same `DocumentAppForm`, reuses the shared document
 * recalculation/validation utils, and exposes `validate()` / `payload()` so a
 * host keeps its own persistence boundary. Every field, fee-line rule,
 * discount/tax calculation and total is therefore identical in both places.
 */
import type { DocumentTabSchema } from '~/types/common'
import type { FreightRecord } from '~/types/record'
import { getFreightModule } from '~/config/freight-modules'
import { recalculateFreightRecord } from '~/utils/freight/document-calculations'
import { validateDocumentFields, validateTableRows } from '~/utils/validation/record-validation'
import { useFormValidation } from '~/composables/common/useFormValidation'
import {
  SERVICE_CHARGE_MODULE_PATH,
  internalFeeLinesTable,
  serviceChargeFormPayload,
  serviceChargeFormTabs,
} from '~/utils/freight/service-charge-form'

const props = withDefaults(defineProps<{
  model: FreightRecord
  tabs?: DocumentTabSchema[]
  /** Page-owned active tab (standalone); omit to manage it in this form. */
  activeTab?: string
  /** The host renders its own tab strip (standalone document page). */
  showTabBar?: boolean
  /** Embedded Service Order tab: only fee lines, no parent header fields. */
  feeLinesOnly?: boolean
  /** Internal charge: cost + selling price, supplier required. */
  internal?: boolean
  readOnly?: boolean
  fieldErrors?: Record<string, string>
  formErrors?: string[]
  onFieldEdit?: (key: string) => void
  onFieldBlur?: (key: string) => void
  wide?: boolean
}>(), {
  tabs: undefined,
  activeTab: undefined,
  showTabBar: true,
  feeLinesOnly: false,
  internal: false,
  readOnly: false,
  fieldErrors: undefined,
  formErrors: undefined,
  onFieldEdit: undefined,
  onFieldBlur: undefined,
  wide: false,
})

const emit = defineEmits<{
  'update:model': [record: FreightRecord]
}>()

const { t } = useI18n()
const module = getFreightModule(SERVICE_CHARGE_MODULE_PATH)!
const internalTab = ref('general')

const active = computed({
  get: () => props.activeTab || internalTab.value,
  set: (value: string) => {
    internalTab.value = value
  },
})

const tabs = computed(() => {
  if (props.tabs?.length) {
    return props.feeLinesOnly ? props.tabs.filter(tab => tab.id === 'fee-lines') : props.tabs
  }
  return serviceChargeFormTabs(module, props.model, {
    linkedToOrder: true,
    feeLinesOnly: props.feeLinesOnly,
  })
})

watch(tabs, (value) => {
  if (!value.some(tab => tab.id === active.value)) active.value = value[0]?.id || 'general'
}, { immediate: true })

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: key => String(module.fields.find(field => field.key === key)?.label || key),
  order: () => [
    ...module.fields.map(field => field.key),
    ...((module.tables || [])
      .filter(table => table.key === 'feeLines')
      .flatMap(table => Array.from({ length: (props.model.feeLines as unknown[] | undefined)?.length || 0 })
        .flatMap((_, index) => table.columns.map(column => `${table.key}.${index}.${column.key}`)))),
  ],
})

const shownFieldErrors = computed(() => props.fieldErrors ?? validation.fieldErrors.value)
const shownFormErrors = computed(() => props.formErrors ?? validation.formErrors.value)

function onEdit(key: string) {
  props.onFieldEdit?.(key)
  validation.clearFieldError(key)
}

function fieldValue(key: string) {
  return props.model[key]
}

function setFieldValue(key: string, value: unknown) {
  if (key === 'permissionRows') return
  const next = recalculateFreightRecord(module, {
    ...props.model,
    [key]: value,
  } as FreightRecord)
  emit('update:model', next)
}

function validate(): boolean {
  validation.reset()
  const failures = props.feeLinesOnly
    ? []
    : validateDocumentFields({
        fields: module.fields.filter(field => !field.computed),
        model: props.model as Record<string, unknown>,
        isCreate: !props.model.id,
        label: key => String(module.fields.find(field => field.key === key)?.label || key),
      })
  const internal = props.internal || String(props.model.chargeSide || '').toUpperCase() === 'INTERNAL'
  for (const table of (internal ? [internalFeeLinesTable(module)] : (module.tables || []))) {
    if (table.key !== 'feeLines') continue
    failures.push(...validateTableRows({
      table,
      rows: Array.isArray(props.model.feeLines) ? props.model.feeLines as Array<Record<string, unknown>> : [],
      label: key => String(module.fields.find(field => field.key === key)?.label || key),
      columnLabel: column => column.label || column.key,
    }))
  }
  validation.applyFailures(failures)
  if ((props.internal || String(props.model.chargeSide || '').toUpperCase() === 'INTERNAL')
    && !String(props.model.supplierPartyId || '').trim()) {
    validation.setFieldError('supplierPartyId', t('validation.required', { field: t('freight.ui.supplier') }))
    return false
  }
  return failures.length === 0
}

function payload(): FreightRecord {
  return serviceChargeFormPayload(props.model)
}

function applyServerError(error: unknown) {
  validation.applyServerError(error)
}

function resetErrors() {
  validation.reset()
}

defineExpose({ validate, payload, applyServerError, resetErrors, validation })
</script>

<template>
  <div class="min-w-0 w-full">
    <CommonAppFormErrorSummary
      v-if="shownFormErrors.length"
      class="pt-4"
      :form-errors="shownFormErrors" />
    <DocumentAppDocumentTabBar
      v-if="showTabBar && tabs.length > 1"
      :tabs="tabs"
      :active-tab="active"
      @update:active-tab="active = $event" />
    <DocumentAppDocumentForm
      :tabs="tabs"
      :active-tab="active"
      :field-value="fieldValue"
      :set-field-value="setFieldValue"
      :read-only="readOnly"
      :field-errors="shownFieldErrors"
      :on-field-edit="onEdit"
      :on-field-blur="onFieldBlur"
      :wide="wide" />
  </div>
</template>
