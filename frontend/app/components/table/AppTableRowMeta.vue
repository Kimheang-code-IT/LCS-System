<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

withDefaults(defineProps<{
  items: DropdownMenuItem[][]
  loading?: boolean
  /** Record identifier for the trigger's accessible name ("Actions for INV…"). */
  label?: string
}>(), {
  loading: false,
  label: '',
})

const { t } = useI18n()
</script>

<template>
  <div class="flex items-center justify-center gap-2">
    <UDropdownMenu :items="items" :content="{ align: 'end' }" :aria-label="t('freight.ui.actions')">
      <UButton
        icon="i-lucide-ellipsis"
        color="neutral"
        variant="ghost"
        size="xs"
        :loading="loading"
        :aria-label="label ? t('freight.ui.actionsForRecord', { record: label }) : t('freight.ui.actions')"
      />
    </UDropdownMenu>
  </div>
</template>
