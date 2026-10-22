<script setup lang="ts">
import type { ComponentTabRuntime } from '~/types/component-config'

/**
 * Read-only render of a configuration snapshot (tabs -> groups -> fields).
 * Shared by the version detail page and the publish-live form so both always
 * show the same structure.
 */
withDefaults(defineProps<{
  tabs: ComponentTabRuntime[]
  tradeDirections?: Record<string, string>
  description?: string
  emptyText?: string
  loading?: boolean
}>(), {
  tradeDirections: () => ({}),
  description: '',
  emptyText: '',
  loading: false,
})

function tradeDirection(tab: ComponentTabRuntime, directions: Record<string, string>) {
  if (!tab.tradeDirectionId) return 'Shared / all directions'
  return directions[tab.tradeDirectionId] || `#${tab.tradeDirectionId}`
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-base font-semibold">Configuration details</h2>
          <p v-if="description" class="text-sm text-muted">{{ description }}</p>
        </div>
        <UBadge color="neutral" variant="subtle" size="sm">{{ tabs.length }} tabs</UBadge>
      </div>
    </template>

    <div v-if="loading" class="space-y-2">
      <USkeleton v-for="index in 6" :key="index" class="h-9 w-full" />
    </div>
    <div v-else-if="!tabs.length" class="text-sm text-muted">
      {{ emptyText }}
    </div>
    <div v-else class="space-y-5">
      <section
        v-for="tab in tabs"
        :key="tab.id"
        class="space-y-3 rounded-lg border border-default p-3"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="font-semibold">{{ tab.name }} <span class="text-xs text-muted">{{ tab.code }}</span></h3>
            <p class="text-xs text-muted">Trade direction: {{ tradeDirection(tab, tradeDirections) }}</p>
          </div>
          <UBadge color="neutral" variant="subtle" size="sm">{{ tab.groups?.length || 0 }} groups</UBadge>
        </div>

        <div v-for="group in tab.groups || []" :key="group.id" class="rounded-md bg-elevated/50 p-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-medium">{{ group.name }}</span>
            <UBadge color="info" variant="subtle" size="sm">{{ group.displayMode || group.renderMode }}</UBadge>
            <UBadge color="neutral" variant="subtle" size="sm">{{ group.dataCardinality || 'multiple' }}</UBadge>
            <span class="text-xs text-muted">{{ group.formColumns || 3 }} column layout</span>
            <span v-if="group.editable === false" class="text-xs text-warning">Read-only</span>
          </div>

          <div class="mt-2 overflow-x-auto">
            <table class="w-full min-w-max text-sm">
              <thead class="text-left text-xs uppercase text-muted">
                <tr>
                  <th class="px-2 py-1 font-medium">Order</th>
                  <th class="px-2 py-1 font-medium">Field</th>
                  <th class="px-2 py-1 font-medium">Code</th>
                  <th class="px-2 py-1 font-medium">Data Type</th>
                  <th class="px-2 py-1 font-medium">Required</th>
                  <th class="px-2 py-1 font-medium">Visible</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="attribute in group.attributes || []" :key="attribute.id" class="border-t border-default">
                  <td class="px-2 py-1 tabular-nums text-muted">{{ attribute.sortOrder }}</td>
                  <td class="px-2 py-1 font-medium">{{ attribute.label }}</td>
                  <td class="px-2 py-1 font-mono text-xs">{{ attribute.code }}</td>
                  <td class="px-2 py-1">{{ attribute.fieldType }}</td>
                  <td class="px-2 py-1">{{ attribute.isRequired ? 'Yes' : 'No' }}</td>
                  <td class="px-2 py-1">{{ attribute.isVisible === false ? 'No' : 'Yes' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </UCard>
</template>
