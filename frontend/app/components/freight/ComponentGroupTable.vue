<script setup lang="ts">
import type { ComponentTabGroup } from '~/types/freight/component-config'
import { componentGroupToFreightTable } from '~/utils/freight/component-tabs'

const props = defineProps<{
  group: ComponentTabGroup
  references: Record<string, Record<string, string>>
  modelValue: Array<Record<string, unknown>>
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'save': []
}>()

const table = computed(() => componentGroupToFreightTable(props.group, props.references))
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
