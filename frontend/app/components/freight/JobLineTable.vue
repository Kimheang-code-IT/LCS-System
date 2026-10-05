<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'

defineProps<{
  table: FreightTable
  modelValue: Array<Record<string, unknown>>
  disabled?: boolean
  viewOnlyActions?: boolean
  rowDisabled?: (row: Record<string, unknown>) => boolean
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
  rowActions?: (action: string, row: Record<string, unknown>) => {
    label: string
    icon: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  } | null
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
  <FreightAppLineTable
    :table="table"
    :model-value="modelValue"
    :disabled="disabled"
    :view-only-actions="viewOnlyActions"
    :row-disabled="rowDisabled"
    :extra-row-menu-items="extraRowMenuItems"
    :row-inline-actions="rowInlineActions"
    :row-actions="rowActions"
    :header-actions="headerActions"
    @update:model-value="emit('update:modelValue', $event)"
    @row-action="(action, row) => emit('rowAction', action, row)" />
</template>
