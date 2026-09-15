<script setup lang="ts">
import type { TimelineItem } from '@nuxt/ui'
import type { ActivityEvent, EntityComment, PersonSummary } from '~/types/docetra/common'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const props = withDefaults(defineProps<{
  comments: EntityComment[]
  activity: ActivityEvent[]
  commentBody: string
  submitting?: boolean
  canComment?: boolean
  currentUser?: PersonSummary
  showComposer?: boolean
  showNewEmail?: boolean
  updatingCommentId?: string | null
  deletingCommentId?: string | null
  hasMore?: boolean
  loadingMore?: boolean
}>(), {
  canComment: true,
  showComposer: true,
  showNewEmail: true,
  submitting: false,
  updatingCommentId: null,
  deletingCommentId: null,
  hasMore: false,
  loadingMore: false,
})

const emit = defineEmits<{
  'update:commentBody': [string]
  submit: []
  updateComment: [payload: { id: string, body: string }]
  deleteComment: [id: string]
  loadMore: []
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

function formatRelativeStamp(value: string) {
  return relativeTime(value, relativeLabels.value)
}

const showInput = computed(() => props.canComment && props.showComposer)

type FeedKind = 'comment' | 'attachment' | 'event'

type ActivityTimelineItem = TimelineItem & {
  kind: FeedKind
  value: string
  at: number
  comment?: EntityComment
  event?: ActivityEvent
  highlight?: string | null
  slot?: 'comment' | 'line'
}

const timelineItems = computed<ActivityTimelineItem[]>(() => {
  const commentItems: ActivityTimelineItem[] = props.comments.map(comment => ({
    kind: 'comment' as const,
    value: `comment-${comment.id}`,
    at: new Date(comment.createdAt).getTime(),
    comment,
    icon: 'i-lucide-message-square',
    title: `${personLabel(comment.author.name)} ${t('docetra.comments.commented')}`,
    date: formatRelativeStamp(comment.createdAt),
    slot: 'comment' as const,
  }))

  const eventItems: ActivityTimelineItem[] = props.activity
    .filter(event => !['commented', 'comment'].includes(event.action))
    .map((event) => {
      const attachment = isAttachmentEvent(event.action)
      return {
        kind: (attachment ? 'attachment' : 'event') as FeedKind,
        value: `event-${event.id}`,
        at: new Date(event.occurredAt).getTime(),
        event,
        highlight: eventHighlight(event),
        icon: attachment ? 'i-lucide-paperclip' : 'i-lucide-circle',
        title: eventPrefix(event),
        date: formatRelativeStamp(event.occurredAt),
        slot: 'line' as const,
      }
    })

  return [...commentItems, ...eventItems].sort((a, b) => b.at - a.at)
})

function personLabel(name?: string) {
  const current = props.currentUser?.name
  if (!name) return t('docetra.activity.system')
  if (current && name === current) return t('docetra.meta.you')
  if (name === 'You' || name === t('docetra.meta.you')) return t('docetra.meta.you')
  return name
}

function isAttachmentEvent(action: string) {
  return action.toLowerCase().includes('attach')
}

function eventHighlight(event: ActivityEvent): string | null {
  const meta = event.metadata || {}
  if (typeof meta.fileName === 'string') return meta.fileName
  if (typeof meta.filename === 'string') return meta.filename
  if (typeof meta.attachment === 'string') return meta.attachment
  return null
}

function eventPrefix(event: ActivityEvent) {
  const actor = personLabel(event.actor?.name)
  const action = event.action.toLowerCase()

  if (action.includes('attach')) {
    return `${actor} ${t('docetra.activity.attached')}`
  }
  if (action.includes('creat')) {
    return `${actor} ${t('docetra.activity.createdThis')}`
  }
  if (action.includes('updat') || action.includes('edit')) {
    return `${actor} ${t('docetra.activity.lastEditedThis')}`
  }
  if (action.includes('assign')) {
    return event.summary
  }
  return event.summary
}

function onSubmit() {
  if (!props.commentBody.trim() || props.submitting) return
  emit('submit')
}

function asFeedItem(item: TimelineItem): ActivityTimelineItem {
  return item as ActivityTimelineItem
}

const editingCommentId = ref<string | null>(null)
const editingBody = ref('')
const submittedEditBody = ref<string | null>(null)

function canManageComment(comment?: EntityComment) {
  if (!props.canComment || !comment || !props.currentUser) return false
  return comment.author.id === props.currentUser.id
    || Boolean(comment.author.email && comment.author.email === props.currentUser.email)
    || comment.author.name === props.currentUser.name
}

function startEditing(comment: EntityComment) {
  if (!canManageComment(comment)) return
  editingCommentId.value = comment.id
  editingBody.value = comment.body
}

function cancelEditing() {
  editingCommentId.value = null
  editingBody.value = ''
  submittedEditBody.value = null
}

function saveEditing(comment: EntityComment) {
  const body = editingBody.value.trim()
  if (!body || props.updatingCommentId) return
  submittedEditBody.value = body
  emit('updateComment', { id: comment.id, body })
}

watch(() => props.updatingCommentId, (current, previous) => {
  if (current || !previous || previous !== editingCommentId.value || !submittedEditBody.value) return
  const updated = props.comments.find(comment => comment.id === previous)
  if (updated?.body === submittedEditBody.value) cancelEditing()
  else submittedEditBody.value = null
})

watch(() => props.comments.map(comment => comment.id), (ids) => {
  if (editingCommentId.value && !ids.includes(editingCommentId.value)) cancelEditing()
})

function commentActions(comment: EntityComment) {
  return [[
    {
      label: t('actions.delete'),
      icon: 'i-lucide-trash',
      color: 'error' as const,
      disabled: Boolean(props.deletingCommentId),
      onSelect: () => emit('deleteComment', comment.id),
    },
  ]]
}
</script>

<template>
  <div class="relative space-y-8 border-t border-default py-6">
    <!-- Comments -->
    <section class="space-y-3">
      <h2 class="text-base font-semibold text-highlighted">
        {{ $t('docetra.comments.title') }}
        <span class="font-normal text-muted">({{ comments.length }})</span>
      </h2>

      <div v-if="showInput" class="flex items-center gap-3">
        <UAvatar
          :alt="currentUser?.name || $t('docetra.meta.you')"
          size="sm"
        />
        <UInput
          :model-value="commentBody"
          :placeholder="$t('docetra.comments.placeholder')"
          color="neutral"
          variant="soft"
          size="md"
          class="w-full"
          :disabled="submitting"
          @update:model-value="(v: string | number) => emit('update:commentBody', String(v ?? ''))"
          @keydown.enter.exact.prevent="onSubmit"
        >
          <template #trailing>
            <UButton
              icon="i-lucide-send"
              color="primary"
              variant="ghost"
              size="xs"
              square
              :aria-label="$t('docetra.confirm.submit')"
              :loading="submitting"
              :disabled="!commentBody.trim() || submitting"
              @click="onSubmit"
            />
          </template>
        </UInput>
      </div>
    </section>

    <!-- Activity -->
    <section class="space-y-4">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-base font-semibold text-highlighted">
          {{ $t('docetra.activity.title') }}
        </h2>
      </div>

      <UTimeline
        v-if="timelineItems.length"
        :items="timelineItems"
        color="neutral"
        size="xs"
        class="w-full"
        :default-value="timelineItems[timelineItems.length - 1]?.value"
        :ui="{
          item: 'pb-1 last:pb-0',
          container: 'items-center',
          indicator: 'z-10 size-6 shrink-0 bg-default text-muted ring ring-default',
          separator: 'w-px min-h-4 flex-1 bg-gray-200 dark:bg-gray-700',
          wrapper: 'ms-1 pb-5',
          date: 'hidden',
          title: 'text-sm font-normal text-toned',
          description: 'hidden',
        }"
      >
        <!-- Comment card -->
        <template #comment-title="{ item }">
          <UCard
            variant="outline"
            :ui="{
              root: 'w-full',
              header: 'flex items-center gap-2.5 p-3 sm:px-3',
              body: 'p-3 pt-0 sm:p-3 sm:pt-0 ps-10 sm:ps-10',
            }"
          >
            <template #header>
              <UAvatar
                v-if="asFeedItem(item).comment"
                :alt="asFeedItem(item).comment!.author.name"
                size="xs"
              />
              <p class="min-w-0 flex-1 truncate text-sm text-toned">
                <span class="font-medium text-highlighted">{{ asFeedItem(item).title }}</span>
                <span class="text-muted"> • {{ asFeedItem(item).date }}</span>
              </p>
              <div v-if="canManageComment(asFeedItem(item).comment)" class="flex shrink-0 items-center">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="link"
                  class="px-1"
                  :label="$t('actions.edit')"
                  :disabled="Boolean(updatingCommentId || deletingCommentId)"
                  @click="startEditing(asFeedItem(item).comment!)"
                />
                <UDropdownMenu :items="commentActions(asFeedItem(item).comment!)">
                  <UButton
                    icon="i-lucide-ellipsis"
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    square
                    :loading="deletingCommentId === asFeedItem(item).comment!.id"
                    :disabled="Boolean(updatingCommentId || deletingCommentId)"
                  />
                </UDropdownMenu>
              </div>
            </template>

            <div v-if="editingCommentId === asFeedItem(item).comment?.id" class="space-y-2">
              <UTextarea
                v-model="editingBody"
                :placeholder="$t('docetra.comments.editPlaceholder')"
                :rows="3"
                autoresize
                autofocus
                class="w-full"
                :disabled="updatingCommentId === asFeedItem(item).comment?.id"
                @keydown.ctrl.enter.prevent="saveEditing(asFeedItem(item).comment!)"
                @keydown.meta.enter.prevent="saveEditing(asFeedItem(item).comment!)"
                @keydown.esc.prevent="cancelEditing"
              />
              <div class="flex justify-end gap-2">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  :label="$t('actions.cancel')"
                  :disabled="updatingCommentId === asFeedItem(item).comment?.id"
                  @click="cancelEditing"
                />
                <UButton
                  size="xs"
                  icon="i-lucide-check"
                  :label="$t('actions.save')"
                  :loading="updatingCommentId === asFeedItem(item).comment?.id"
                  :disabled="!editingBody.trim()"
                  @click="saveEditing(asFeedItem(item).comment!)"
                />
              </div>
            </div>
            <p v-else class="whitespace-pre-wrap text-sm text-highlighted">
              {{ asFeedItem(item).comment?.body }}
              <span v-if="asFeedItem(item).comment?.editedAt" class="ms-1 text-xs text-muted">
                ({{ $t('docetra.comments.edited') }})
              </span>
            </p>
          </UCard>
        </template>

        <!-- Attachment / event text line -->
        <template #line-title="{ item }">
          <p class="text-sm leading-relaxed text-toned">
            <span class="text-highlighted">{{ asFeedItem(item).title }}</span>
            <template v-if="asFeedItem(item).highlight">
              {{ ' ' }}
              <span class="font-medium text-highlighted">{{ asFeedItem(item).highlight }}</span>
            </template>
            <span class="text-muted"> • {{ asFeedItem(item).date }}</span>
          </p>
        </template>

        <!-- Tiny bullet for plain events -->
        <template #indicator="{ item }">
          <span
            v-if="asFeedItem(item).kind === 'event'"
            class="size-2 rounded-full bg-gray-700 dark:bg-gray-300"
          />
          <UIcon
            v-else
            :name="asFeedItem(item).icon || 'i-lucide-circle'"
            class="size-3.5"
          />
        </template>
      </UTimeline>

      <p v-else class="text-sm text-muted">{{ $t('docetra.activity.empty') }}</p>

      <div v-if="hasMore" class="flex justify-center pt-2">
        <UButton
          color="neutral"
          variant="soft"
          icon="i-lucide-chevrons-down"
          :loading="loadingMore"
          @click="emit('loadMore')"
        >
          {{ $t('docetra.actions.loadMore') }}
        </UButton>
      </div>
    </section>
  </div>
</template>
