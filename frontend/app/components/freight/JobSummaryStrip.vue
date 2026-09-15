<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

export type JobSummaryItem = {
  label: string
  value: string
  to?: string | RouteLocationRaw
}

defineProps<{
  items: JobSummaryItem[]
}>()
</script>

<template>
  <div class="flex flex-wrap items-stretch divide-x divide-default overflow-hidden rounded-md border border-default bg-default">
    <template v-for="item in items" :key="item.label">
      <ULink
        v-if="item.to"
        :to="item.to"
        class="flex min-w-28 flex-1 flex-col gap-0.5 px-3 py-2 transition-colors hover:bg-muted/60"
      >
        <span class="text-[11px] font-medium uppercase tracking-wide text-muted">{{ item.label }}</span>
        <span class="text-sm font-semibold tabular-nums text-highlighted">{{ item.value }}</span>
      </ULink>
      <div v-else class="flex min-w-28 flex-1 flex-col gap-0.5 px-3 py-2">
        <span class="text-[11px] font-medium uppercase tracking-wide text-muted">{{ item.label }}</span>
        <span class="text-sm font-semibold tabular-nums text-highlighted">{{ item.value }}</span>
      </div>
    </template>
  </div>
</template>
