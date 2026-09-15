<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'

defineProps<{
  table: FreightTable
  modelValue: Array<Record<string, unknown>>
  disabled?: boolean
  viewOnlyActions?: boolean
  extraRowMenuItems?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  }>
  rowInlineActions?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  }>
  headerActions?: Array<{
    label: string
    icon?: string
    disabled?: boolean
    onClick: () => void
  }>
}>()

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'rowAction': [action: 'view', row: Record<string, unknown>]
}>()
</script>

<template>
  <TableAppLineTable
    :table="table"
    :model-value="modelValue"
    :disabled="disabled"
    :view-only-actions="viewOnlyActions"
    :extra-row-menu-items="extraRowMenuItems"
    :row-inline-actions="rowInlineActions"
    :header-actions="headerActions"
    @update:model-value="emit('update:modelValue', $event)"
    @row-action="(action, row) => emit('rowAction', action, row)" />
</template>
