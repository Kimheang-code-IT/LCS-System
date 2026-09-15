<script setup lang="ts">
import { useFreightRouteModule } from '~/composables/freight/useFreight'

const { module } = useFreightRouteModule()
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
    <FreightReportsView v-if="module?.kind === 'reports'" />
    <FreightJobDetail v-else-if="module?.kind === 'job'" />
    <FreightDocumentView v-else-if="module" />
    <div v-else class="grid h-full min-h-0 flex-1 place-items-center p-8">
      <UEmpty
        variant="naked"
        icon="i-lucide-unplug"
        title="This page is not wired yet"
        description="The workspace could not resolve a module for this route."
      />
    </div>
  </div>
</template>
