<script setup lang="ts">
import type { ComponentTabRuntime } from '~/types/component-config'

withDefaults(defineProps<{
  tab: ComponentTabRuntime
  references?: Record<string, Record<string, string>>
  rowsByGroup: Record<string, Array<Record<string, unknown>>>
  editable?: boolean
  saving?: boolean
  loading?: boolean
  /** Page-level failure while loading the dynamic configuration. */
  error?: string | null
  /** Cell errors keyed `<groupId>.<rowIndex>.<attributeCode>`. */
  fieldErrors?: Record<string, string>
  /** Fired on any edit so the host can clear that cell's error. */
  onFieldEdit?: (key: string) => void
}>(), {
  references: () => ({}),
  editable: true,
  saving: false,
  loading: false,
  error: null,
  fieldErrors: () => ({}),
  onFieldEdit: undefined,
})

const emit = defineEmits<{
  'update:rows': [groupId: string, rows: Array<Record<string, unknown>>]
  'save-group': [groupId: string]
}>()
</script>

<template>
  <DocumentDynamicTabRenderer
    :tab="tab"
    :references="references"
    :rows-by-group="rowsByGroup"
    :editable="editable"
    :saving="saving"
    :loading="loading"
    :error="error"
    :field-errors="fieldErrors"
    :on-field-edit="onFieldEdit"
    @update:rows="(groupId, rows) => emit('update:rows', groupId, rows)"
    @save-group="groupId => emit('save-group', groupId)"
  />
</template>
