<script setup lang="ts">
import type { ButtonProps } from '@nuxt/ui'

withDefaults(defineProps<{
  title: string
  description?: string
  icon?: string
  actions?: ButtonProps[]
}>(), {
  icon: 'i-lucide-inbox',
  actions: () => [],
})
</script>

<template>
  <UEmpty
    variant="naked"
    size="sm"
    :icon="icon"
    :title="title"
    :description="description"
    :actions="actions"
    class="rounded-md border border-dashed border-default py-6"
  />
</template>
