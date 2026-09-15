<script setup lang="ts">
definePageMeta({
  titleKey: 'freight.nav.reports',
  middleware: ['report-area-auth'],
})
</script>

<template>
  <FreightReportsView />
</template>
