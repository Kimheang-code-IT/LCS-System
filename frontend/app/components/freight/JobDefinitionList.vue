<script setup lang="ts">
import { displayText } from '~/utils/freight/job-workspace'

export type JobDefinitionItem = {
  label: string
  value?: unknown
  span?: 1 | 2
}

defineProps<{
  items: JobDefinitionItem[]
}>()
</script>

<template>
  <dl class="grid grid-cols-1 gap-2 sm:grid-cols-2">
    <div
      v-for="item in items"
      :key="item.label"
      class="rounded-md border border-default bg-default px-3 py-2"
      :class="item.span === 2 ? 'sm:col-span-2' : ''"
    >
      <dt class="text-[11px] font-medium uppercase tracking-wide text-muted">{{ item.label }}</dt>
      <dd class="mt-0.5 text-sm font-medium text-highlighted">{{ displayText(item.value) }}</dd>
    </div>
  </dl>
</template>
