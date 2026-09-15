<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'

const props = defineProps<{
  table: FreightTable | null
  modelValue: Array<Record<string, unknown>>
  disabled?: boolean
  saving?: boolean
}>()

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
    <TableAppLineTable
      v-if="table"
      :table="table"
      :model-value="modelValue"
      :disabled="disabled"
      :header-actions="headerActions"
      @update:model-value="emit('update:modelValue', $event)" />
    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noColumnsConfigured')"
      :description="t('freight.ui.noColumnsConfiguredHint')"
      icon="i-lucide-columns-3" />
  </div>
</template>
