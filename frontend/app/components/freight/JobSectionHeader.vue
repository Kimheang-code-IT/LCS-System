<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="flex flex-wrap items-start justify-between gap-2">
    <div class="min-w-0">
      <h3 class="text-sm font-semibold text-highlighted">{{ title }}</h3>
      <p v-if="description" class="mt-0.5 text-xs text-muted">{{ description }}</p>
    </div>
    <div class="flex flex-wrap items-center justify-end gap-1.5">
      <slot name="actions" />
    </div>
  </div>
</template>
