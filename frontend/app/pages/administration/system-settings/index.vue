<script setup lang="ts">
import SystemSettingsPage from '~/components/document/SystemSettingsPage.vue'

definePageMeta({ titleKey: 'freight.pages.settings', permission: 'settings.app_config.view' })
</script>

<template>
  <SystemSettingsPage />
</template>
