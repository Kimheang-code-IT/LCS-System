<script setup lang="ts">
import type { DynamicTab } from '~/types/freight/dynamic-tabs'
import { dynamicTabToFreightTable } from '~/utils/freight/dynamic-tab-columns'

const props = defineProps<{
  tab: DynamicTab
  references: Record<string, Record<string, string>>
  modelValue: Array<Record<string, unknown>>
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'save': []
}>()

const table = computed(() => dynamicTabToFreightTable(props.tab, props.references))
</script>

<template>
  <FreightDynamicDataTable
    :table="table"
    :model-value="modelValue"
    :disabled="!editable"
    :saving="saving"
    @update:model-value="emit('update:modelValue', $event)"
    @save="emit('save')" />
</template>
