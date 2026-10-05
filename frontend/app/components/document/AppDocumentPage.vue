<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type {
  ActivityEvent,
  AttachmentMeta,
  DocumentTabSchema,
  EntityComment,
} from '~/types/common'
import { useConfirm } from '~/composables/common/useConfirm'
import type { ExportRequest } from '~/types/export'

const props = withDefaults(defineProps<{
  tabs: DocumentTabSchema[]
  activeTab: string
  fieldValue: (key: string) => unknown
  setFieldValue: (key: string, value: unknown) => void | Promise<void>
  pending?: boolean
  saving?: boolean
  error?: string | null
  notFound?: boolean
  readOnly?: boolean
  canSave?: boolean
  saveLabel?: string
  showSave?: boolean
  showComments?: boolean
  showTabs?: boolean
  showListNav?: boolean
  canNavigatePrevious?: boolean
  canNavigateNext?: boolean
  loadingListNavigation?: boolean
  listNavigationDirection?: 'previous' | 'next' | null
  listTo?: string
  isCreate?: boolean
  /** Force the wider document content shell (matches App Config settings width). */
  contentWide?: boolean
  canComment?: boolean
  comments?: EntityComment[]
  activity?: ActivityEvent[]
  attachments?: AttachmentMeta[]
  commentBody?: string
  submittingComment?: boolean
  updatingCommentId?: string | null
  deletingCommentId?: string | null
  hasMoreFeed?: boolean
  loadingMoreFeed?: boolean
  currentUser?: { id: string, name: string, email?: string }
  moreItems?: DropdownMenuItem[][]
  exporting?: boolean
  canExport?: boolean
  confirmSave?: boolean
  showCancel?: boolean
}>(), {
  saveLabel: '',
  listTo: '',
  currentUser: undefined,
  metaTitle: '',
  metaSubtitle: '',
  metaIcon: '',
  metaStatus: '',
  metaStage: '',
  metaOwner: undefined,
  metaAssignee: undefined,
  metaCreatedAt: '',
  metaUpdatedAt: '',
  moreItems: () => [],
  pending: false,
  saving: false,
  error: null,
  notFound: false,
  readOnly: false,
  canSave: true,
  showSave: true,
  showComments: false,
  showTabs: true,
  showListNav: false,
  canNavigatePrevious: false,
  canNavigateNext: false,
  loadingListNavigation: false,
  listNavigationDirection: null,
  isCreate: false,
  contentWide: false,
  canComment: true,
  comments: () => [],
  activity: () => [],
  attachments: () => [],
  commentBody: '',
  submittingComment: false,
  updatingCommentId: null,
  deletingCommentId: null,
  hasMoreFeed: false,
  loadingMoreFeed: false,
  exporting: false,
  canExport: true,
  confirmSave: true,
  showCancel: false,
})

const emit = defineEmits<{
  'update:activeTab': [string]
  'update:commentBody': [string]
  'update:attachments': [AttachmentMeta[]]
  save: []
  refresh: []
  submitComment: []
  updateComment: [id: string, body: string]
  deleteComment: [id: string]
  loadMoreFeed: []
  navigatePrevious: []
  navigateNext: []
  export: [request: ExportRequest]
}>()

const { t } = useI18n()

const exportFields = computed(() => {
  if (!props.canExport) return []
  const fields = props.tabs.flatMap(tab =>
    tab.sections.flatMap(section =>
      section.fields
        .filter(field =>
          field.type !== 'secret'
          && field.type !== 'alert'
          && field.type !== 'line-table'
          && field.type !== 'related-records'
          && field.type !== 'permission-matrix',
        )
        .map(field => ({
          label: field.label || t(field.labelKey),
          value: field.key,
        })),
    ),
  )
  return [...new Map(fields.map(field => [field.value, field])).values()]
})

const showForm = computed(() =>
  !props.notFound && !props.error && (!props.pending || props.tabs.length > 0),
)

const { confirm } = useConfirm()

const scrollEl = ref<HTMLElement | null>(null)
const showScrollTop = ref(false)

function onFormScroll() {
  showScrollTop.value = (scrollEl.value?.scrollTop ?? 0) > 240
}

function scrollToTop() {
  scrollEl.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

function selectTab(value: string) {
  emit('update:activeTab', value)
  scrollEl.value?.scrollTo({ top: 0 })
}

async function onSaveClick() {
  if (!props.confirmSave) {
    emit('save')
    return
  }
  const ok = await confirm({
    kind: props.isCreate ? 'submit' : 'save',
  })
  if (ok) emit('save')
}
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-default">
    <LayoutAppHeaderPageActions
:can-create="false"
:refreshing="pending"
:more-items="moreItems"
      :export-fields="exportFields"
:exporting="exporting"
:show-list-nav="showListNav"
:list-to="listTo"
      :can-navigate-previous="canNavigatePrevious"
:can-navigate-next="canNavigateNext"
      :loading-list-navigation="loadingListNavigation"
:list-navigation-direction="listNavigationDirection"
      :is-create="isCreate"
:show-save="showSave && canSave && !readOnly"
:save-label="saveLabel"
:saving="saving"
      :show-cancel="showCancel && Boolean(listTo)"
:cancel-to="listTo"
      @refresh="emit('refresh')"
@export="emit('export', $event)"
@navigate-previous="emit('navigatePrevious')"
      @navigate-next="emit('navigateNext')"
@save="onSaveClick">
      <template v-if="$slots.leading" #leading>
        <slot name="leading" />
      </template>
      <slot name="actions" />
    </LayoutAppHeaderPageActions>

    <div class="relative flex min-h-0 w-full min-w-0 flex-1 overflow-hidden p-0">
      <div
v-if="pending"
        class="absolute inset-0 z-10 flex items-center justify-center bg-default/50 backdrop-blur-[1px]">
        <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-primary" />
      </div>

      <div class="relative flex min-h-0 w-full min-w-0 flex-1 overflow-hidden bg-default">
        <div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <DocumentAppDocumentTabBar
v-if="showTabs && showForm && !notFound && !error"
:tabs="tabs"
            :active-tab="activeTab"
@update:active-tab="selectTab" />

          <div ref="scrollEl" class="min-h-0 min-w-0 flex-1 overflow-auto" @scroll.passive="onFormScroll">
            <UAlert
v-if="notFound"
class="mx-auto mt-6 w-full px-4 sm:px-6 lg:px-10"
:class="contentWide
              ? 'max-w-5xl lg:max-w-6xl xl:max-w-7xl'
              : 'max-w-2xl sm:max-w-3xl lg:max-w-4xl'"
color="error"
:title="t('lcs.states.notFound')" />
            <UAlert
v-else-if="error"
class="mx-auto mt-6 w-full px-4 sm:px-6 lg:px-10"
:class="contentWide
              ? 'max-w-5xl lg:max-w-6xl xl:max-w-7xl'
              : 'max-w-2xl sm:max-w-3xl lg:max-w-4xl'"
color="error"
:title="error" />

            <template v-else-if="showForm">
              <slot name="before-form" />

              <div
class="flex min-h-0 w-full"
                :class="$slots.aside ? 'flex-col xl:flex-row' : 'flex-col'">
                <div class="min-w-0 flex-1">
                  <slot name="form">
                    <DocumentAppDocumentForm
:tabs="tabs"
:active-tab="activeTab"
:field-value="fieldValue"
                      :set-field-value="setFieldValue"
:read-only="readOnly"
:wide="contentWide" />
                  </slot>

                  <DocumentAppDocumentContentShell v-if="showComments && !isCreate" :wide="contentWide">
                    <DocumentAppCommentsActivity
:comments="comments"
:activity="activity"
:comment-body="commentBody"
                      :submitting="submittingComment"
:updating-comment-id="updatingCommentId"
                      :deleting-comment-id="deletingCommentId"
:has-more="hasMoreFeed"
:loading-more="loadingMoreFeed"
                      :can-comment="canComment"
:current-user="currentUser"
                      @update:comment-body="emit('update:commentBody', $event)"
@submit="emit('submitComment')"
                      @update-comment="emit('updateComment', $event.id, $event.body)"
                      @delete-comment="emit('deleteComment', $event)"
@load-more="emit('loadMoreFeed')" />
                  </DocumentAppDocumentContentShell>

                  <DocumentAppDocumentContentShell
v-if="$slots['after-form']"
:wide="contentWide"
                    class="space-y-3 pb-6">
                    <slot name="after-form" />
                  </DocumentAppDocumentContentShell>
                </div>

                <aside
v-if="$slots.aside"
                  class="w-full shrink-0 border-t border-default px-4 py-6 sm:px-6 xl:w-80 xl:border-t-0 xl:border-l xl:overflow-y-auto">
                  <slot name="aside" />
                </aside>
              </div>
            </template>
          </div>

          <UButton
v-show="showScrollTop && showForm"
icon="i-lucide-chevron-up"
color="neutral"
variant="soft"
            size="sm"
square
class="absolute bottom-4 right-4 z-20 border border-default shadow-sm"
            :aria-label="t('lcs.document.scrollToTop')"
@click="scrollToTop" />
        </div>
      </div>
    </div>
  </div>
</template>
