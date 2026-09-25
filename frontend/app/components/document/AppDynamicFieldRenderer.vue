<script setup lang="ts">
import type {
  ConnectionStatusFieldValue,
  DocumentFieldSchema,
  FieldOption,
} from '~/types/docetra/common'
import type {
  AttributeDataType,
  AttributeOption,
  ConfigWorkflowStage,
  RecordAttribute,
  RecordTypeAttribute,
  RecordTypeNumbering,
  ValidationRule,
  VisibilityRule,
  WorkflowTransition,
} from '~/types/docetra/configuration'
import type { ConnectionStatus, NotificationRule, TelegramDestination } from '~/types/docetra/settings'
import { TELEGRAM_TEMPLATE_VARIABLES } from '~/types/docetra/settings'
import { createClientId } from '~/utils/client-id'
import { TELEGRAM_DESTINATION_TYPE_OPTIONS } from '~/utils/constants/select-options'
import { resolveFieldHelp } from '~/utils/field-help'
import { useReferenceOptions } from '~/composables/common/useReferenceOptions'
import type { FreightRelated, FreightTable } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import { asNumber } from '~/composables/freight/useFreight'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import {
  freightDocumentLineActionKey,
  freightDocumentLineTableHeaderKey,
  freightDocumentModelKey,
  freightDocumentRecordKey,
} from '~/utils/freight/document-tabs'
import { resolveDynamicFieldKind } from '~/composables/freight/useDynamicFieldRegistry'

const props = defineProps<{
  field: DocumentFieldSchema
  modelValue: unknown
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [unknown]
}>()

const { t, te } = useI18n()
const { loadReferenceOptions } = useReferenceOptions()

const hintOpen = ref(false)

const destinationTypeItems = TELEGRAM_DESTINATION_TYPE_OPTIONS

const stringValue = computed({
  get: () => String(props.modelValue ?? ''),
  set: (v: string) => emit('update:modelValue', v),
})

const selectValue = computed({
  get: () => {
    if (props.modelValue == null || props.modelValue === '') return undefined
    return String(props.modelValue)
  },
  set: (v: string | undefined) => emit('update:modelValue', v ?? ''),
})

const numberValue = computed({
  get: () => (typeof props.modelValue === 'number' ? props.modelValue : Number(props.modelValue || 0)),
  set: (v: number | null) => emit('update:modelValue', v ?? 0),
})

const boolValue = computed({
  get: () => {
    const trueValue = props.field.meta?.trueValue
    if (trueValue !== undefined) return props.modelValue === trueValue || props.modelValue === true
    if (typeof props.modelValue === 'string') {
      const value = props.modelValue.trim().toLowerCase()
      if (['no', 'false', '0', ''].includes(value)) return false
      if (['yes', 'true', '1'].includes(value)) return true
    }
    return Boolean(props.modelValue)
  },
  set: (v: boolean | 'indeterminate') => {
    const checked = v === true
    const trueValue = props.field.meta?.trueValue
    const falseValue = props.field.meta?.falseValue
    if (trueValue !== undefined) {
      emit('update:modelValue', checked ? trueValue : (falseValue ?? ''))
      return
    }
    emit('update:modelValue', checked)
  },
})

const multiValue = computed({
  get: () => (Array.isArray(props.modelValue)
    ? props.modelValue.map(String).filter(Boolean)
    : (props.modelValue ? [String(props.modelValue)] : [])),
  set: (v: string | string[]) => emit('update:modelValue', v),
})

const permissionRows = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as unknown[] : []),
  set: (v: unknown[]) => emit('update:modelValue', v),
})

const csvValue = computed({
  get: () => Array.isArray(props.modelValue)
    ? (props.modelValue as unknown[]).map(String).join(', ')
    : String(props.modelValue ?? ''),
  set: (v: string) => {
    emit(
      'update:modelValue',
      String(v || '')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
    )
  },
})

const imageValue = computed({
  get: () => (props.modelValue == null || props.modelValue === ''
    ? undefined
    : String(props.modelValue)),
  set: (v: string | undefined) => emit('update:modelValue', v),
})

const colorValue = computed({
  get: () => String(props.modelValue || '#2563eb'),
  set: (v: string) => emit('update:modelValue', v),
})

const secretValue = computed({
  get: () => String(props.modelValue ?? ''),
  set: (v: string) => emit('update:modelValue', v),
})

const destinationsValue = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as TelegramDestination[] : []),
  set: (v: TelegramDestination[]) => emit('update:modelValue', v),
})

const rulesValue = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as NotificationRule[] : []),
  set: (v: NotificationRule[]) => emit('update:modelValue', v),
})

const connectionValue = computed(() => {
  const raw = props.modelValue as ConnectionStatusFieldValue | null | undefined
  return {
    status: (raw?.status || 'not_tested') as ConnectionStatus,
    message: raw?.message,
    lastTestedAt: raw?.lastTestedAt,
    details: raw?.details,
  }
})

const remoteOptions = ref<FieldOption[]>([])
const optionsPending = ref(false)

const resolvedOptionsEndpoint = computed(() => props.field.optionsEndpoint || undefined)

watch(resolvedOptionsEndpoint, async (endpoint) => {
  remoteOptions.value = []
  if (!endpoint) return
  optionsPending.value = true
  try {
    remoteOptions.value = await loadReferenceOptions(endpoint)
  }
  catch {
    remoteOptions.value = []
  }
  finally {
    optionsPending.value = false
  }
}, { immediate: true })

const searchRemoteOptions = useDebounceFn(async (search: string) => {
  const endpoint = resolvedOptionsEndpoint.value
  if (!endpoint) return
  optionsPending.value = true
  try { remoteOptions.value = await loadReferenceOptions(endpoint, search) }
  finally { optionsPending.value = false }
}, 250)

const selectItems = computed(() =>
  [...(props.field.options || []), ...remoteOptions.value]
    .filter(o => o.value !== '')
    .map(o => ({
      label: o.labelKey ? t(o.labelKey) : o.label,
      value: o.value,
    })),
)

const labelText = computed(() => {
  if (props.field.labelKey && te(props.field.labelKey)) return t(props.field.labelKey)
  if (props.field.label) return props.field.label
  return props.field.labelKey || ''
})

const helpText = computed(() => {
  if (props.field.help) return props.field.help
  return resolveFieldHelp(props.field, labelText.value, t, te)
})

const hintText = computed(() => {
  if (props.field.hintKey && te(props.field.hintKey)) return t(props.field.hintKey)
  return helpText.value
})

const placeholderText = computed(() => {
  if (props.field.placeholder) return props.field.placeholder
  if (props.field.placeholderKey && te(props.field.placeholderKey)) {
    return t(props.field.placeholderKey)
  }
  return labelText.value
})

const isBoolean = computed(() => props.field.type === 'boolean')
const fieldKind = computed(() => resolveDynamicFieldKind(props.field))
const isPermissionMatrix = computed(() => fieldKind.value === 'permissionMatrix')
const isSecret = computed(() => props.field.type === 'secret')
const isColor = computed(() => props.field.type === 'color')
const isImage = computed(() => props.field.type === 'image')
const isIcon = computed(() => props.field.type === 'icon')
const isTelegramDestinations = computed(() => props.field.type === 'telegram-destinations')
const isNotificationRules = computed(() => props.field.type === 'notification-rules')
const isConnectionStatus = computed(() => props.field.type === 'connection-status')
const isAlert = computed(() => props.field.type === 'alert')
const isAssignedAttributes = computed(() => props.field.type === 'assigned-attributes')
const isWorkflowBuilder = computed(() => props.field.type === 'workflow-builder')
const isNumberingPreview = computed(() => props.field.type === 'numbering-preview')
const isValidationBuilder = computed(() => props.field.type === 'validation-builder')
const isOptionsBuilder = computed(() => props.field.type === 'options-builder')
const isVisibilityBuilder = computed(() => props.field.type === 'visibility-builder')
const isLineTable = computed(() => props.field.type === 'line-table')
const isRelatedRecords = computed(() => props.field.type === 'related-records')
const isDynamicTable = computed(() => props.field.type === 'dynamic-table')
const isFile = computed(() => props.field.type === 'file')

const dynamicTable = computed(() => props.field.meta?.table as FreightTable | undefined)
const dynamicTableRows = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as Array<Record<string, unknown>> : []),
  set: (rows: Array<Record<string, unknown>>) => emit('update:modelValue', rows),
})

const lineAction = inject(freightDocumentLineActionKey, undefined)
const lineTableHeaderActions = inject(freightDocumentLineTableHeaderKey, undefined)
const documentModel = inject(freightDocumentModelKey, null)
const recordAccess = inject(freightDocumentRecordKey, null)

const lineTable = computed(() => props.field.meta?.table as FreightTable | undefined)
const lineRows = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as Array<Record<string, unknown>> : []),
  set: (rows: Array<Record<string, unknown>>) => emit('update:modelValue', rows),
})
const relatedGroups = computed(() =>
  Array.isArray(props.modelValue)
    ? props.modelValue as Array<FreightRelated & { rows: FreightRecord[] }>
    : [],
)
const showPricingTotals = computed(() => Boolean(props.field.meta?.showPricingTotals))
const includeTaxTotal = computed(() => Boolean(props.field.meta?.includeTax))
const lineCompact = computed(() => Boolean(props.field.meta?.compact))
const lineViewOnly = computed(() => Boolean(props.field.meta?.viewOnly || props.field.readOnly))
const lineHeaderActions = computed(() => {
  if (!lineTableHeaderActions || !lineTable.value) return []
  if (lineTable.value.key === 'feeLines' && documentModel?.value) {
    void documentModel.value.feeLines
  }
  return lineTableHeaderActions(lineTable.value.key)
})

const { formatMoney } = useAppLocalization()

const documentCurrency = computed(() => String(recordAccess?.get('currency') || '').trim() || undefined)

function moneyAmount(key: string) {
  return asNumber(recordAccess?.get(key))
}

function moneyLabel(value: unknown) {
  return formatMoney(value, documentCurrency.value)
}

function onFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  emit('update:modelValue', file?.name || props.modelValue)
}

const iconValue = computed({
  get: () => String(props.modelValue ?? ''),
  set: (v: string) => emit('update:modelValue', v),
})

const assignedAttributes = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as RecordTypeAttribute[] : []),
  set: (v: RecordTypeAttribute[]) => emit('update:modelValue', v),
})

const attributeCatalog = computed(() =>
  (Array.isArray(props.field.meta?.catalog) ? props.field.meta!.catalog as RecordAttribute[] : []),
)

const assignmentStageItems = computed(() => {
  const configured = Array.isArray(props.field.meta?.stages)
    ? props.field.meta.stages as ConfigWorkflowStage[]
    : []
  return [
    { label: t('docetra.config.allStages'), value: '__all_stages__' },
    ...[...configured]
      .sort((a, b) => a.order - b.order)
      .map(stage => ({ label: stage.name, value: stage.code })),
  ]
})

const selectedAttributeId = ref<string>()
const searchAttributes = computed(() =>
  props.field.meta?.searchAttributes as ((query: string) => void) | undefined,
)

function goCreateAttribute() {}

function goOpenAttribute(_attributeId: string) {}

const workflowValue = computed({
  get: () => {
    const raw = props.modelValue as { stages?: ConfigWorkflowStage[], transitions?: WorkflowTransition[] } | null
    return {
      stages: raw?.stages || [],
      transitions: raw?.transitions || [],
    }
  },
  set: (v: { stages: ConfigWorkflowStage[], transitions: WorkflowTransition[] }) => emit('update:modelValue', v),
})

const workflowStages = computed({
  get: () => workflowValue.value.stages,
  set: (stages: ConfigWorkflowStage[]) => {
    workflowValue.value = { ...workflowValue.value, stages }
  },
})

const workflowTransitions = computed({
  get: () => workflowValue.value.transitions,
  set: (transitions: WorkflowTransition[]) => {
    workflowValue.value = { ...workflowValue.value, transitions }
  },
})

const numberingPreview = computed(() =>
  (props.modelValue && typeof props.modelValue === 'object'
    ? props.modelValue as RecordTypeNumbering
    : { prefix: 'DOC', sequenceLength: 4, includeYear: true, resetYearly: true }),
)

const validationValue = computed({
  get: () => (props.modelValue && typeof props.modelValue === 'object' ? props.modelValue as ValidationRule : {}),
  set: (v: ValidationRule) => emit('update:modelValue', v),
})

const validationDataType = computed(() =>
  (props.field.meta?.dataType as AttributeDataType) || 'short_text',
)

const optionsBuilderValue = computed({
  get: () => (Array.isArray(props.modelValue) ? props.modelValue as AttributeOption[] : []),
  set: (v: AttributeOption[]) => emit('update:modelValue', v),
})

const visibilityValue = computed({
  get: () => (props.modelValue == null ? null : props.modelValue as VisibilityRule),
  set: (v: VisibilityRule | null) => emit('update:modelValue', v),
})

const visibilityFieldOptions = computed(() =>
  (props.field.options || []).map(o => ({
    label: o.labelKey ? t(o.labelKey) : o.label,
    value: o.value,
  })),
)

function addAssignedAttribute() {
  const id = selectedAttributeId.value
  if (!id) return
  const attr = attributeCatalog.value.find(a => a.id === id)
  if (!attr) return
  const row: RecordTypeAttribute = {
    attributeId: attr.id,
    attributeCode: attr.code,
    attributeLabel: attr.label,
    dataType: attr.dataType,
    required: attr.required,
    readOnly: attr.readOnly,
    visible: true,
    searchable: attr.searchable,
    filterable: attr.filterable,
    showInList: attr.showInList,
    section: 'General',
    order: assignedAttributes.value.length,
  }
  assignedAttributes.value = [...assignedAttributes.value, row]
  selectedAttributeId.value = undefined
}

function updateAssigned(id: string, patch: Partial<RecordTypeAttribute>) {
  assignedAttributes.value = assignedAttributes.value.map(a =>
    a.attributeId === id ? { ...a, ...patch } : a,
  )
}

function removeAssigned(id: string) {
  assignedAttributes.value = assignedAttributes.value
    .filter(a => a.attributeId !== id)
    .map((a, index) => ({ ...a, order: index }))
}

function onReorderAssigned(items: Array<RecordTypeAttribute & { id: string }>) {
  assignedAttributes.value = items.map((a, index) => ({
    attributeId: a.attributeId,
    attributeCode: a.attributeCode,
    attributeLabel: a.attributeLabel,
    dataType: a.dataType,
    required: a.required,
    readOnly: a.readOnly,
    visible: a.visible,
    searchable: a.searchable,
    filterable: a.filterable,
    showInList: a.showInList,
    stageCode: a.stageCode,
    section: a.section,
    order: index,
  }))
}

const textareaHelp = computed(() => {
  if (props.field.key === 'telegram.messageTemplate') {
    return TELEGRAM_TEMPLATE_VARIABLES.join(' ')
  }
  return helpText.value
})

/** Textareas: min 3 lines, grow with content up to 7. */
const TEXTAREA_MIN_ROWS = 3
const TEXTAREA_MAX_ROWS = 7

const textareaRows = computed(() => {
  const requested = props.field.rows ?? TEXTAREA_MIN_ROWS
  return Math.min(TEXTAREA_MAX_ROWS, Math.max(TEXTAREA_MIN_ROWS, requested))
})

function toggleHint() {
  hintOpen.value = !hintOpen.value
}

function closeHint() {
  hintOpen.value = false
}

watch(() => props.field.key, () => {
  hintOpen.value = false
})

function addDestination() {
  const next: TelegramDestination = {
    id: createClientId('td'),
    name: 'New destination',
    type: 'chat',
    chatId: '',
    enabledEvents: ['record_created'],
    status: 'not_tested',
    enabled: true,
  }
  destinationsValue.value = [...destinationsValue.value, next]
}

function removeDestination(id: string) {
  destinationsValue.value = destinationsValue.value.filter(d => d.id !== id)
}
</script>

<template>
  <CommonAppRolePermissionMatrix
    v-if="isPermissionMatrix"
    v-model="permissionRows"
    :disabled="disabled || field.readOnly"
  />

  <div
    v-else-if="isLineTable && lineTable"
    class="space-y-6 md:col-span-2"
  >
    <TableAppLineTable
      :table="lineTable"
      :model-value="lineRows"
      :disabled="disabled || lineViewOnly"
      :compact="lineCompact"
      :view-only-actions="lineViewOnly"
      :header-actions="lineHeaderActions"
      @update:model-value="lineRows = $event"
      @row-action="(action, row) => lineAction?.(action, row)"
    />
    <div
      v-if="showPricingTotals"
      class="ms-auto grid w-full max-w-sm gap-1 px-1 py-1.5 text-xs"
    >
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ $t('freight.fields.subtotal') }}</span>
        <span class="font-medium text-highlighted">{{ moneyLabel(moneyAmount('subtotal')) }}</span>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ $t('freight.fields.discount') }}</span>
        <span class="font-medium text-highlighted">− {{ moneyLabel(moneyAmount('discount')) }}</span>
      </div>
      <div
        v-if="includeTaxTotal"
        class="flex items-center justify-between gap-4"
      >
        <span class="text-muted">{{ $t('freight.fields.tax') }}</span>
        <span class="font-medium text-highlighted">{{ moneyLabel(moneyAmount('tax')) }}</span>
      </div>
      <div class="mt-1 flex items-center justify-between gap-4 border-t border-default pt-2 text-base">
        <span class="font-semibold text-highlighted">{{ $t('freight.fields.total') }}</span>
        <span class="font-bold text-primary">{{ moneyLabel(moneyAmount('total')) }}</span>
      </div>
    </div>
  </div>

  <TableAppRelatedRecords
    v-else-if="isRelatedRecords"
    class="md:col-span-2"
    :groups="relatedGroups"
  />

  <UFormField
    v-else-if="isDynamicTable && dynamicTable"
    :label="labelText"
    :help="helpText"
    :required="field.required"
    class="md:col-span-2"
  >
    <DocumentAppDynamicTableField
      v-model="dynamicTableRows"
      :table="dynamicTable"
      :disabled="disabled || field.readOnly"
    />
  </UFormField>

  <UAlert
    v-else-if="isAlert"
    class="md:col-span-2"
    :color="field.alertColor || 'warning'"
    variant="subtle"
    :title="labelText"
    :description="helpText || undefined"
  />

  <CommonAppSecretInput
    v-else-if="isSecret"
    v-model="secretValue"
    :label="labelText"
    :help="helpText"
    :disabled="disabled || field.readOnly"
  />

  <CommonAppColorPicker
    v-else-if="isColor"
    v-model="colorValue"
    :label="labelText"
    :help="helpText"
    :disabled="disabled || field.readOnly"
  />

  <CommonAppImageUploadField
    v-else-if="isImage"
    v-model="imageValue"
    :label="labelText"
    :help="helpText"
    :disabled="disabled || field.readOnly"
  />

  <CommonAppIconPicker
    v-else-if="isIcon"
    v-model="iconValue"
    :label="labelText"
    :help="helpText"
    :disabled="disabled || field.readOnly"
  />

  <ConfigurationAppNumberingPreview
    v-else-if="isNumberingPreview"
    class="md:col-span-2"
    :numbering="numberingPreview"
  />

  <ConfigurationAppValidationRuleBuilder
    v-else-if="isValidationBuilder"
    v-model="validationValue"
    class="md:col-span-2"
    :data-type="validationDataType"
  />

  <ConfigurationAppAttributeOptionsBuilder
    v-else-if="isOptionsBuilder"
    v-model="optionsBuilderValue"
    class="md:col-span-2"
  />

  <ConfigurationAppVisibilityRuleBuilder
    v-else-if="isVisibilityBuilder"
    v-model="visibilityValue"
    class="md:col-span-2"
    :field-options="visibilityFieldOptions"
  />

  <div v-else-if="isWorkflowBuilder" class="md:col-span-2">
    <ConfigurationAppWorkflowStageBuilder
      v-model:stages="workflowStages"
      v-model:transitions="workflowTransitions"
    />
  </div>

  <div
    v-else-if="isAssignedAttributes"
    class="space-y-4 md:col-span-2"
  >
    <div class="flex flex-wrap items-end gap-2">
      <UFormField :label="t('docetra.config.assignAttribute')" class="min-w-64 flex-1" :help="t('docetra.fieldHelp.assignAttribute')">
        <UInputMenu
          v-model="selectedAttributeId"
          :items="selectItems"
          value-key="value"
          class="w-full"
          :disabled="disabled || field.readOnly"
          :loading="optionsPending"
          @update:search-term="searchAttributes?.($event)"
        />
      </UFormField>
      <UButton
        icon="i-lucide-plus"
        :disabled="!selectedAttributeId || disabled || field.readOnly"
        @click="addAssignedAttribute"
      >
        {{ t('docetra.config.addAttribute') }}
      </UButton>
      <UButton
        icon="i-lucide-list-plus"
        color="neutral"
        variant="outline"
        :disabled="disabled || field.readOnly"
        @click="goCreateAttribute"
      >
        {{ t('docetra.config.createAttribute') }}
      </UButton>
    </div>

    <CommonAppSortableList
      :items="assignedAttributes.map(a => ({ ...a, id: a.attributeId }))"
      @reorder="onReorderAssigned($event as any)"
    >
      <template #default="{ item }">
        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <div>
              <p class="text-sm font-medium">
                {{ item.attributeLabel }}
              </p>
              <p class="text-xs text-muted">
                {{ item.attributeCode }} · {{ item.dataType }}
              </p>
            </div>
            <div class="flex items-center gap-1">
              <UButton
                icon="i-lucide-external-link"
                color="neutral"
                variant="ghost"
                size="xs"
                :aria-label="t('docetra.config.openAttribute')"
                @click="goOpenAttribute(item.attributeId)"
              />
              <UButton
                icon="i-lucide-trash-2"
                color="error"
                variant="ghost"
                size="xs"
                :disabled="disabled || field.readOnly"
                @click="removeAssigned(item.attributeId)"
              />
            </div>
          </div>
          <div class="grid gap-2 sm:grid-cols-3">
            <UCheckbox
              :model-value="item.required"
              :label="t('docetra.fields.required')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { required: Boolean($event) })"
            />
            <UCheckbox
              :model-value="item.readOnly"
              :label="t('docetra.config.readOnly')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { readOnly: Boolean($event) })"
            />
            <UCheckbox
              :model-value="item.visible"
              :label="t('docetra.config.visible')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { visible: Boolean($event) })"
            />
            <UCheckbox
              :model-value="item.searchable"
              :label="t('docetra.config.searchable')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { searchable: Boolean($event) })"
            />
            <UCheckbox
              :model-value="item.filterable"
              :label="t('docetra.config.filterable')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { filterable: Boolean($event) })"
            />
            <UCheckbox
              :model-value="item.showInList"
              :label="t('docetra.config.showInList')"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { showInList: Boolean($event) })"
            />
          </div>
          <UInput
            :model-value="item.section || ''"
            size="sm"
            :placeholder="t('docetra.config.section')"
            :disabled="disabled || field.readOnly"
            @update:model-value="updateAssigned(item.attributeId, { section: String($event) })"
          />
          <UFormField :label="t('docetra.config.assignedStage')" :help="t('docetra.fieldHelp.assignedStage')">
            <USelect
              :model-value="item.stageCode || '__all_stages__'"
              :items="assignmentStageItems"
              value-key="value"
              label-key="label"
              size="sm"
              class="w-full"
              :disabled="disabled || field.readOnly"
              @update:model-value="updateAssigned(item.attributeId, { stageCode: $event === '__all_stages__' ? undefined : String($event || '') || undefined })"
            />
          </UFormField>
        </div>
      </template>
      <template #empty>
        {{ t('docetra.config.noAssignedAttributes') }}
      </template>
    </CommonAppSortableList>
  </div>

  <div
    v-else-if="isTelegramDestinations"
    class="space-y-3 md:col-span-2"
  >
    <div class="flex items-center justify-between">
      <h4 class="text-sm font-semibold">
        {{ t('docetra.settings.destinations') }}
      </h4>
      <UButton
        size="sm"
        icon="i-lucide-plus"
        :disabled="disabled || field.readOnly"
        @click="addDestination"
      >
        {{ t('docetra.settings.addDestination') }}
      </UButton>
    </div>

    <div
      v-for="dest in destinationsValue"
      :key="dest.id"
      class="grid gap-2 rounded-lg border border-default p-3 md:grid-cols-4"
    >
      <UInput
        v-model="dest.name"
        :placeholder="t('docetra.fields.name')"
        :disabled="disabled || field.readOnly"
      />
      <UInput
        v-model="dest.chatId"
        placeholder="Chat ID"
        :disabled="disabled || field.readOnly"
      />
      <USelect
        v-model="dest.type"
        :items="destinationTypeItems"
        value-key="value"
        label-key="label"
        :disabled="disabled || field.readOnly"
      />
      <div class="flex items-center justify-between gap-2">
        <USwitch v-model="dest.enabled" :disabled="disabled || field.readOnly" />
        <UButton
          icon="i-lucide-trash-2"
          color="error"
          variant="ghost"
          size="xs"
          :disabled="disabled || field.readOnly"
          @click="removeDestination(dest.id)"
        />
      </div>
    </div>
  </div>

  <div
    v-else-if="isNotificationRules"
    class="space-y-2 md:col-span-2"
  >
    <p class="text-sm font-medium">
      {{ t('docetra.settings.eventRules') }}
    </p>
    <div
      v-for="rule in rulesValue"
      :key="rule.id"
      class="flex items-center justify-between rounded-md border border-default px-3 py-2"
    >
      <span class="text-sm">{{ rule.event }}</span>
      <USwitch v-model="rule.enabled" :disabled="disabled || field.readOnly" />
    </div>
  </div>

  <CommonAppConnectionStatusCard
    v-else-if="isConnectionStatus"
    class="md:col-span-2"
    :status="connectionValue.status"
    :title="labelText"
    :message="connectionValue.message"
    :last-tested-at="connectionValue.lastTestedAt"
    :details="connectionValue.details"
  />

  <!-- Checkbox: label beside control + helper text below -->
  <UFormField
    v-else-if="isBoolean"
    :help="helpText"
  >
    <div class="flex min-h-11 flex-wrap items-center gap-2 pt-1">
      <UCheckbox
        v-model="boolValue"
        :disabled="disabled || field.readOnly"
        :required="field.required"
        size="md"
        :ui="{ label: 'text-base text-highlighted' }"
      >
        <template #label>
          <span class="inline-flex items-center gap-1.5">
            <span>{{ labelText }}</span>
            <UButton
              v-if="hintText"
              icon="i-lucide-info"
              color="neutral"
              variant="ghost"
              size="xs"
              square
              class="text-muted"
              :aria-label="hintText"
              @click.prevent.stop="toggleHint"
            />
          </span>
        </template>
      </UCheckbox>

      <div
        v-if="hintText && hintOpen"
        class="inline-flex max-w-md items-start gap-2 rounded-md border border-default bg-elevated px-2.5 py-1.5 text-xs text-toned"
      >
        <p class="min-w-0 flex-1 leading-relaxed">{{ hintText }}</p>
        <UButton
          icon="i-lucide-x"
          color="neutral"
          variant="soft"
          size="xs"
          square
          class="shrink-0"
          @click="closeHint"
        />
      </div>
    </div>
  </UFormField>

  <!-- Standard fields: label + control + help below -->
  <UFormField
    v-else
    :label="labelText"
    :required="field.required"
    :help="field.type === 'textarea' && textareaHelp ? textareaHelp : helpText"
  >
    <div class="flex items-start gap-1.5">
      <div class="min-w-0 flex-1">
        <UTextarea
          v-if="field.type === 'textarea'"
          v-model="stringValue"
          :disabled="disabled || field.readOnly"
          :placeholder="placeholderText"
          :rows="textareaRows"
          :maxrows="TEXTAREA_MAX_ROWS"
          autoresize
          size="md"
          class="w-full"
          :class="field.key === 'telegram.messageTemplate' ? 'font-mono text-sm' : ''"
        />
        <UInputNumber
          v-else-if="field.type === 'number'"
          v-model="numberValue"
          :disabled="disabled || field.readOnly"
          :increment="false"
          :decrement="false"
          size="md"
          class="w-full"
        />
        <CommonAppInputDate
          v-else-if="field.type === 'date'"
          v-model="stringValue"
          :disabled="disabled || field.readOnly"
          :required="field.required"
          size="md"
          class="w-full"
        />
        <CommonAppInputDate
          v-else-if="field.type === 'datetime'"
          v-model="stringValue"
          granularity="minute"
          :disabled="disabled || field.readOnly"
          :required="field.required"
          size="md"
          class="w-full"
        />
        <UInputMenu
          v-else-if="field.type === 'select' && field.optionsEndpoint"
          v-model="selectValue"
          :items="selectItems"
          value-key="value"
          :placeholder="placeholderText"
          :disabled="disabled || field.readOnly"
          :loading="optionsPending"
          size="md"
          class="w-full"
          @update:search-term="searchRemoteOptions"
        />
        <USelect
          v-else-if="field.type === 'select'"
          v-model="selectValue"
          :items="selectItems"
          value-key="value"
          :placeholder="placeholderText"
          :disabled="disabled || field.readOnly"
          :loading="optionsPending"
          size="md"
          class="w-full"
        />
        <CommonAppMentionMultiInput
          v-else-if="field.type === 'multiselect'"
          v-model="multiValue"
          :items="selectItems"
          :placeholder="placeholderText"
          :disabled="disabled || field.readOnly"
          :loading="optionsPending"
          @search="searchRemoteOptions"
        />
        <UInput
          v-else-if="field.type === 'csv-list'"
          v-model="csvValue"
          :placeholder="placeholderText"
          :disabled="disabled || field.readOnly"
          size="md"
          class="w-full"
        />
        <UInput
          v-else-if="isFile"
          type="file"
          :disabled="disabled || field.readOnly"
          size="md"
          class="w-full"
          @change="onFileChange"
        />
        <UInput
          v-else
          v-model="stringValue"
          :type="field.type === 'url' ? 'url' : 'text'"
          :placeholder="placeholderText"
          :disabled="disabled || field.readOnly"
          size="md"
          class="w-full"
        />
      </div>

      <UButton
        v-if="field.hintKey && hintText"
        icon="i-lucide-info"
        color="neutral"
        variant="ghost"
        size="xs"
        square
        class="mt-1.5 shrink-0 text-muted"
        @click="toggleHint"
      />
    </div>

    <div
      v-if="field.hintKey && hintText && hintOpen"
      class="mt-2 flex items-start gap-2 rounded-md border border-default bg-elevated px-2.5 py-1.5 text-xs text-toned"
    >
      <p class="min-w-0 flex-1 leading-relaxed">{{ hintText }}</p>
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="soft"
        size="xs"
        square
        class="shrink-0"
        @click="closeHint"
      />
    </div>
  </UFormField>
</template>
