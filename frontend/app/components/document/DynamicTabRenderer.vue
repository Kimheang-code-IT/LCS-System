<script setup lang="ts">
import type { ComponentTabRuntime } from '~/types/component-config'

const props = withDefaults(defineProps<{
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

/** Groups are already ordered by the backend's tab display order. */
const groups = computed(() => props.tab.groups)
</script>

<template>
  <div class="space-y-8">
    <div v-if="loading && !groups.length" class="space-y-3" aria-busy="true">
      <USkeleton class="h-4 w-40" />
      <USkeleton class="h-24 w-full" />
      <USkeleton class="h-4 w-32" />
      <USkeleton class="h-24 w-full" />
    </div>

    <div
      v-else-if="error"
      role="alert"
      class="rounded-lg border border-error/40 bg-error/5 p-3 text-sm text-error"
    >
      {{ error }}
    </div>

    <template v-else>
      <DocumentDynamicGroupRenderer
        v-for="group in groups"
        :key="group.id"
        :group="group"
        :rows="rowsByGroup[group.id] || []"
        :references="references"
        :editable="editable"
        :saving="saving"
        :field-errors="fieldErrors"
        :on-field-edit="onFieldEdit"
        @update:rows="(rows) => emit('update:rows', group.id, rows)"
        @save-group="emit('save-group', group.id)"
      />

      <FreightJobEmptyState
        v-if="!groups.length"
        :title="$t('freight.ui.noColumnsConfigured')"
        :description="$t('freight.ui.noColumnsConfiguredHint')"
        icon="i-lucide-columns-3"
      />
    </template>
  </div>
</template>
