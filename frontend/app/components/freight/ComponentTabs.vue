<script setup lang="ts">
import type { ComponentTabRuntime } from '~/types/freight/component-config'

defineProps<{
  tab: ComponentTabRuntime
  references: Record<string, Record<string, string>>
  rowsByGroup: Record<string, Array<Record<string, unknown>>>
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:rows': [groupId: string, rows: Array<Record<string, unknown>>]
  'save-group': [groupId: string]
}>()
</script>

<template>
  <div class="space-y-8">
    <section v-for="group in tab.groups" :key="group.id" class="space-y-3">
      <h3 class="text-sm font-semibold text-highlighted">{{ group.name }}</h3>
      <FreightComponentGroupTable
        v-if="group.renderMode === 'table'"
        :group="group"
        :references="references"
        :model-value="rowsByGroup[group.id] || []"
        :editable="editable"
        :saving="saving"
        @update:model-value="emit('update:rows', group.id, $event)"
        @save="emit('save-group', group.id)" />
      <FreightComponentGroupForm
        v-else
        :group="group"
        :references="references"
        :model-value="rowsByGroup[group.id] || []"
        :editable="editable"
        :saving="saving"
        @update:model-value="emit('update:rows', group.id, $event)"
        @save="emit('save-group', group.id)" />
    </section>

    <FreightJobEmptyState
      v-if="!tab.groups.length"
      :title="$t('freight.ui.noColumnsConfigured')"
      :description="$t('freight.ui.noColumnsConfiguredHint')"
      icon="i-lucide-columns-3" />
  </div>
</template>
