<script setup lang="ts">
import type { TimelineItem } from '@nuxt/ui'
import type { ActivityEvent, PersonSummary } from '~/types/docetra/common'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const props = defineProps<{
  title?: string
  subtitle?: string
  /** Module icon shown in the record tile instead of the first letter. */
  icon?: string
  owner?: PersonSummary
  activity?: ActivityEvent[]
  createdAt?: string
  updatedAt?: string
}>()

const { t } = useI18n()
const { relativeTime } = useAppLocalization()

const relativeLabels = computed(() => ({
  justNow: t('docetra.meta.justNow'),
  minuteAgo: t('docetra.meta.minuteAgo'),
  minutesAgo: (n: number) => t('docetra.meta.minutesAgo', { n }),
  hourAgo: t('docetra.meta.hourAgo'),
  hoursAgo: (n: number) => t('docetra.meta.hoursAgo', { n }),
  dayAgo: t('docetra.meta.dayAgo'),
  daysAgo: (n: number) => t('docetra.meta.daysAgo', { n }),
}))

function formatRelativeStamp(value?: string) {
  if (!value) return ''
  return relativeTime(value, relativeLabels.value, { fallback: value })
}

const initial = computed(() => {
  const text = (props.title || '').trim()
  return text ? text.charAt(0).toUpperCase() : '—'
})

const auditItems = computed<TimelineItem[]>(() => {
  const events = [...(props.activity || [])]
    .sort((a, b) => String(b.occurredAt).localeCompare(String(a.occurredAt)))

  if (events.length) {
    return events.map((event, index) => {
      const result = event.metadata?.result ? String(event.metadata.result) : ''
      const remark = event.metadata?.remark ? String(event.metadata.remark) : ''
      return {
        value: event.id || index,
        date: formatRelativeStamp(event.occurredAt) || event.occurredAt,
        title: event.summary || event.action,
        description: [event.actor?.name, result, remark].filter(Boolean).join(' · '),
        icon: 'i-lucide-history',
      }
    })
  }

  const fallback: TimelineItem[] = []
  if (props.updatedAt) {
    fallback.push({
      value: 'updated',
      date: formatRelativeStamp(props.updatedAt),
      title: `${t('docetra.meta.lastEditedBy')} ${t('docetra.meta.you')}`,
      icon: 'i-lucide-pencil',
    })
  }
  if (props.createdAt) {
    fallback.push({
      value: 'created',
      date: formatRelativeStamp(props.createdAt),
      title: `${t('docetra.meta.createdBy')} ${props.owner?.name || t('docetra.meta.you')}`,
      icon: 'i-lucide-plus',
    })
  }
  return fallback
})
</script>

<template>
  <aside class="flex w-full shrink-0 flex-col border-default bg-default lg:w-64 xl:w-72 lg:border-s">
    <section class="flex items-start gap-3 border-b border-default p-4">
      <div class="grid size-14 shrink-0 place-items-center rounded-lg bg-elevated">
        <UIcon v-if="icon" :name="icon" class="size-7 text-toned" />
        <span v-else class="text-xl font-semibold text-toned">{{ initial }}</span>
      </div>
      <div class="min-w-0 flex-1 pt-0.5">
        <p class="truncate text-sm font-semibold text-highlighted">{{ title || '—' }}</p>
        <p v-if="subtitle" class="mt-0.5 truncate text-xs text-muted">{{ subtitle }}</p>
      </div>
    </section>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      <div class="mb-3 flex items-center gap-2 text-sm text-toned">
        <UIcon name="i-lucide-history" class="size-4 shrink-0" />
        <span class="font-medium">{{ $t('docetra.activity.title') }}</span>
      </div>
      <UTimeline
        v-if="auditItems.length"
        :items="auditItems"
        color="neutral"
        size="xs"
        class="w-full"
        :ui="{
          item: 'pb-1 last:pb-0',
          wrapper: 'ms-1 pb-4',
          date: 'text-xs text-muted',
          title: 'text-xs text-toned',
          description: 'text-xs text-muted',
        }"
      />
      <p v-else class="text-xs text-muted">{{ $t('docetra.activity.empty') }}</p>
    </div>
  </aside>
</template>
