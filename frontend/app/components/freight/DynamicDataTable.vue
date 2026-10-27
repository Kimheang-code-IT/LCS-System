<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'

const props = withDefaults(defineProps<{
  table: FreightTable | null
  modelValue: Array<Record<string, unknown>>
  disabled?: boolean
  saving?: boolean
  /** Cell errors keyed `<errorKey>.<rowIndex>.<column>`. */
  fieldErrors?: Record<string, string>
  errorKey?: string
  onCellEdit?: (cellKey: string) => void
  rowInlineActions?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    disabled?: boolean
    loading?: boolean
    onSelect: () => void
  }>
}>(), {
  fieldErrors: undefined,
  errorKey: undefined,
  onCellEdit: undefined,
  rowInlineActions: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'save': []
}>()

const { t } = useI18n()

const headerActions = computed(() => props.disabled
  ? []
  : [{
      label: t('freight.ui.saveChanges'),
      icon: 'i-lucide-save',
      disabled: props.saving,
      onClick: () => emit('save'),
    }])
</script>

<template>
  <div class="space-y-3">
    <FreightAppLineTable
      v-if="table"
      :table="table"
      :model-value="modelValue"
      :disabled="disabled"
      :header-actions="headerActions"
      :field-errors="fieldErrors"
      :error-key="errorKey"
      :on-cell-edit="onCellEdit"
      :row-inline-actions="rowInlineActions"
      @update:model-value="emit('update:modelValue', $event)" />
    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noColumnsConfigured')"
      :description="t('freight.ui.noColumnsConfiguredHint')"
      icon="i-lucide-columns-3" />
  </div>
</template>
