<script setup lang="ts">
import type { ComponentTabAttribute, ComponentTabGroup } from '~/types/component-config'
import {
  componentGroupIsSingleRecord,
  visibleComponentAttributes,
} from '~/utils/freight/component-layout'
import { componentAttributeRule } from '~/utils/validation/component-rules'
import { validateFieldValue } from '~/utils/validation/field-rules'
import { issueMessage } from '~/utils/validation/messages'

const props = withDefaults(defineProps<{
  group: ComponentTabGroup
  rows: Array<Record<string, unknown>>
  references?: Record<string, Record<string, string>>
  editable?: boolean
  saving?: boolean
  /** Cell errors keyed `<groupId>.<rowIndex>.<attributeCode>`. */
  fieldErrors?: Record<string, string>
  onFieldEdit?: (key: string) => void
}>(), {
  references: () => ({}),
  editable: true,
  saving: false,
  fieldErrors: () => ({}),
  onFieldEdit: undefined,
})

const emit = defineEmits<{
  'update:rows': [Array<Record<string, unknown>>]
  'save': []
}>()

const { t, te, locale } = useI18n()

const attributes = computed(() => visibleComponentAttributes(props.group))
const singleRecord = computed(() => componentGroupIsSingleRecord(props.group))
const editingIndex = ref<number | null>(null)
const draft = ref<Record<string, unknown>>({})
const draftErrors = ref<Record<string, string>>({})

function attributeLabel(attribute: ComponentTabAttribute) {
  if (te(`freight.fields.${attribute.code}`)) return t(`freight.fields.${attribute.code}`)
  return String(locale.value === 'km' && attribute.labelKm ? attribute.labelKm : attribute.label)
}

function emptyDraft(): Record<string, unknown> {
  const blank: Record<string, unknown> = {}
  for (const attribute of attributes.value) {
    if (attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean') blank[attribute.code] = false
    else if (['number', 'decimal', 'money'].includes(attribute.fieldType)) blank[attribute.code] = attribute.defaultValue ?? 0
    else if (attribute.fieldType === 'multi_select') blank[attribute.code] = []
    else blank[attribute.code] = attribute.defaultValue ?? ''
  }
  return blank
}

function resetDraft() {
  draft.value = emptyDraft()
  draftErrors.value = {}
  editingIndex.value = null
}

watch(() => props.group.id, resetDraft, { immediate: true })

const isBlankDraft = computed(() => {
  const initial = emptyDraft()
  return attributes.value.every((attribute) => {
    const value = draft.value[attribute.code]
    if (attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean') {
      return value === false || value === undefined
    }
    if (Array.isArray(value)) return value.length === 0
    const text = String(value ?? '').trim()
    if (text === '') return true
    // Numeric blanks default to 0; an untouched 0 is not a record worth adding.
    const fallback = initial[attribute.code]
    return typeof fallback === 'number' && fallback === 0 && Number(value) === 0
  })
})

const hasRequiredAttribute = computed(() => attributes.value.some(attribute => attribute.isRequired))

const addDisabled = computed(() => {
  if (!props.editable || props.saving) return true
  if (editingIndex.value === null && singleRecord.value && props.rows.length >= 1) return true
  // An empty optional-only form has nothing to add; with required fields the
  // click is allowed so the missing value can be reported inline.
  return isBlankDraft.value && !hasRequiredAttribute.value
})

function setDraftField(code: string, value: unknown) {
  draft.value = { ...draft.value, [code]: value }
  if (draftErrors.value[code]) {
    draftErrors.value = Object.fromEntries(
      Object.entries(draftErrors.value).filter(([key]) => key !== code),
    )
  }
}

function validateDraft(): boolean {
  const errors: Record<string, string> = {}
  for (const attribute of attributes.value) {
    const issue = validateFieldValue(draft.value[attribute.code], componentAttributeRule(attribute))
    if (issue) errors[attribute.code] = issueMessage(t, issue, attributeLabel(attribute))
  }
  draftErrors.value = errors
  return Object.keys(errors).length === 0
}

function submitDraft() {
  if (addDisabled.value || !validateDraft()) return
  const entry = { ...draft.value }
  if (editingIndex.value !== null) {
    const index = editingIndex.value
    emit('update:rows', props.rows.map((row, position) => (position === index
      ? { ...row, ...entry, id: row.id, _rowNo: row._rowNo }
      : row)))
  }
  else {
    emit('update:rows', [...props.rows, entry])
  }
  resetDraft()
}

function editRow(index: number) {
  const row = props.rows[index]
  if (!row) return
  const blank = emptyDraft()
  const next: Record<string, unknown> = {}
  for (const attribute of attributes.value) next[attribute.code] = row[attribute.code] ?? blank[attribute.code]
  editingIndex.value = index
  draft.value = next
  draftErrors.value = {}
}

function deleteRow(index: number) {
  emit('update:rows', props.rows.filter((_, position) => position !== index))
  if (editingIndex.value === index) resetDraft()
  else if (editingIndex.value !== null && editingIndex.value > index) editingIndex.value -= 1
}

function rowInlineActions(row: Record<string, unknown>) {
  if (!props.editable) return []
  // AppLineTable hands this callback its own `{...row, _rowIndex}` copy, so the
  // original array position must come from `_rowIndex`, not object identity.
  const reported = Number(row._rowIndex)
  const index = Number.isInteger(reported) && reported >= 0 && reported < props.rows.length
    ? reported
    : props.rows.indexOf(row)
  return [
    {
      label: t('actions.edit'),
      icon: 'i-lucide-pencil',
      color: 'neutral' as const,
      disabled: props.saving,
      onSelect: () => editRow(index),
    },
    {
      label: t('actions.delete'),
      icon: 'i-lucide-trash-2',
      color: 'error' as const,
      disabled: props.saving,
      onSelect: () => deleteRow(index),
    },
  ]
}

const draftFieldPrefix = computed(() => `${props.group.id}.draft`)
</script>

<template>
  <div class="space-y-5">
    <section v-if="editable" class="space-y-3 rounded-lg border border-default bg-elevated/40 p-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-muted">
          {{ editingIndex === null ? t('freight.componentLayout.newRecord') : t('freight.componentLayout.editRecord') }}
        </h4>
        <span v-if="singleRecord && rows.length >= 1 && editingIndex === null" class="text-[11px] text-muted">
          {{ t('freight.componentLayout.editExistingHint') }}
        </span>
      </div>

      <DocumentDynamicFormRenderer
        :group="group"
        :model-value="draft"
        :references="references"
        :editable="editable"
        :errors="draftErrors"
        :field-key-prefix="draftFieldPrefix"
        :show-submit="false"
        @update:field="setDraftField"
      />

      <div class="flex flex-wrap justify-end gap-2">
        <UButton
          v-if="editingIndex !== null"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          :label="t('actions.cancel')"
          @click="resetDraft"
        />
        <UButton
          :icon="editingIndex === null ? 'i-lucide-plus' : 'i-lucide-check'"
          :label="editingIndex === null ? t('freight.ui.addRow') : t('freight.componentLayout.updateRecord')"
          :disabled="addDisabled"
          @click="submitDraft"
        />
      </div>
    </section>

    <section class="space-y-3">
      <h4 class="text-xs font-semibold uppercase tracking-wide text-muted">
        {{ t('freight.componentLayout.savedRecords') }}
      </h4>

      <DocumentDynamicTableRenderer
        v-if="rows.length"
        :group="group"
        :rows="rows"
        :references="references"
        :editable="editable"
        :saving="saving"
        :field-errors="fieldErrors"
        :on-field-edit="onFieldEdit"
        :row-inline-actions="editable ? rowInlineActions : undefined"
        @update:rows="emit('update:rows', $event)"
        @save="emit('save')"
      />
      <FreightJobEmptyState
        v-else
        :title="t('freight.componentLayout.noRecords')"
        :description="t('freight.componentLayout.noRecordsHint')"
        icon="i-lucide-inbox"
      />
    </section>
  </div>
</template>
