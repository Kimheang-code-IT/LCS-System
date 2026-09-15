<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { tableRowActorName, tableRowCommentCount, tableRowInitials, tableRowStamp } from '~/utils/table/row-meta'

const props = withDefaults(defineProps<{
  row: Record<string, unknown>
  items: DropdownMenuItem[][]
  loading?: boolean
}>(), {
  loading: false,
})

const { t } = useI18n()
const { relativeTime } = useAppLocalization()

const stamp = computed(() => tableRowStamp(props.row))
const letters = computed(() => tableRowInitials(props.row))
const actor = computed(() => tableRowActorName(props.row) || letters.value)
const comments = computed(() => tableRowCommentCount(props.row))

const relativeLabels = computed(() => ({
  justNow: t('freight.ui.justNow'),
  minutesAgo: (n: number) => t('freight.ui.minutesAgo', { n }),
  hoursAgo: (n: number) => t('freight.ui.hoursAgo', { n }),
  daysAgo: (n: number) => t('freight.ui.daysAgo', { n }),
}))

const relative = computed(() =>
  relativeTime(stamp.value, relativeLabels.value, { fallback: '—' }),
)
</script>

<template>
  <div class="flex items-center justify-end gap-2">
    <UAvatar
      :text="letters"
      size="2xs"
      :alt="actor"
    />
    <span class="min-w-22 text-xs text-muted" :title="stamp">{{ relative }}</span>
    <span
      class="inline-flex items-center gap-0.5 text-xs text-muted"
      :title="t('freight.ui.comments')"
    >
      <UIcon name="i-lucide-message-square" class="size-3.5" />
      {{ comments }}
    </span>
    <UDropdownMenu :items="items" :content="{ align: 'end' }" :aria-label="t('freight.ui.actions')">
      <UButton
        icon="i-lucide-ellipsis"
        color="neutral"
        variant="ghost"
        size="xs"
        :loading="loading"
        :aria-label="t('freight.ui.actions')"
      />
    </UDropdownMenu>
  </div>
</template>
