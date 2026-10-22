<script setup lang="ts">
/**
 * Shared readable width for document forms / comments / alerts.
 * The narrow variant keeps fields from stretching edge-to-edge; the wide
 * variant is used by forms that embed tables and fills ~95% of the viewport,
 * capped so a table never becomes unreadable on an ultra-wide screen.
 */
withDefaults(defineProps<{
  /** Use for permission matrices, builders, and other dense editors. */
  wide?: boolean
}>(), {
  wide: false,
})
</script>

<template>
  <div
    class="mx-auto w-full"
    :class="wide
      ? 'w-[95%] max-w-[1800px] px-4 sm:px-6 md:px-8 lg:px-10 xl:px-12'
      : 'max-w-2xl px-4 sm:max-w-3xl sm:px-6 md:px-8 lg:max-w-4xl lg:px-10 xl:max-w-5xl xl:px-12'"
  >
    <slot />
  </div>
</template>
