<script setup lang="ts">
import type { ComponentTabRuntime, ConfigurationVersion, ConfigurationVersionActivationEvent, ConfigurationVersionComparison } from '~/types/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { userSourcePermissions } from '~/utils/freight/permissions'
import { snapshotPreviewTabs } from '~/utils/freight/config-version-preview'
import { apiErrorMessage, normalizeApiError } from '~/utils/validation/api-error'

definePageMeta({
  titleKey: 'freight.pages.configurationVersions',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const route = useRoute()
const { confirm } = useConfirm()
const config = useComponentConfig()
const auth = useAuthStore()

const versionId = computed(() => String(route.params.id || ''))
const detail = ref<ConfigurationVersion | null>(null)
const history = ref<ConfigurationVersionActivationEvent[]>([])
const notFound = ref(false)
const loading = ref(false)
const pageErrors = ref<string[]>([])
const name = ref('')

const rollbackOpen = ref(false)
const rollbackReason = ref('')
const rollbackError = ref('')
const rollingBack = ref(false)

const compareOpen = ref(false)
const comparing = ref(false)
const compareFrom = ref('')
const compareTo = ref('')
const compareOptions = ref<ConfigurationVersion[]>([])
const comparison = ref<ConfigurationVersionComparison | null>(null)

type BadgeColor = 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'primary' | 'secondary'

const STATUS_COLORS: Record<ConfigurationVersion['status'], BadgeColor> = {
  DRAFT: 'warning',
  PUBLISHED: 'success',
  RETIRED: 'neutral',
}

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: key => (key === 'changeNote' ? 'Name' : key),
  order: () => ['changeNote'],
})

const permissionCodes = computed(() => new Set<string>(userSourcePermissions(auth.user)))
const pageKeys = computed(() => new Set(auth.user?.pageAccess || auth.user?.permissions || []))

function granted(code: string, pageKey: string) {
  return permissionCodes.value.has(code) || pageKeys.value.has(pageKey)
}

const canManage = computed(() => granted('configuration.manage', 'configuration.edit'))
const canActivate = computed(() => granted('configuration.activate', 'configuration.edit') || canManage.value)
const canRollback = computed(() => granted('configuration.rollback', 'configuration.edit') || canManage.value)
const canCompare = computed(() => granted('configuration.compare', 'configuration.view'))

const activeId = computed(() => config.activeVersion.value?.id || '')
const isActive = computed(() => Boolean(detail.value && detail.value.id === activeId.value))
const isDraft = computed(() => detail.value?.status === 'DRAFT')
const isImmutable = computed(() => Boolean(detail.value) && !isDraft.value)
const canEdit = computed(() => Boolean(detail.value) && isDraft.value && canManage.value)
const canDelete = computed(() => Boolean(detail.value) && isDraft.value && canManage.value)
const canPublishVersion = computed(() => Boolean(detail.value) && !isDraft.value && !isActive.value && canActivate.value)
const canRollbackVersion = computed(() => Boolean(detail.value) && !isDraft.value && !isActive.value && canRollback.value)
const saving = computed(() => config.saving.value)
const previewTabs = computed<ComponentTabRuntime[]>(() => snapshotPreviewTabs(detail.value))
const groupCount = computed(() => previewTabs.value.reduce((total, tab) => total + (tab.groups?.length || 0), 0))
const fieldCount = computed(() => previewTabs.value.reduce(
  (total, tab) => total + (tab.groups || []).reduce((sum, group) => sum + (group.attributes?.length || 0), 0),
  0,
))

function statusColor(version: ConfigurationVersion | null): BadgeColor {
  return version ? STATUS_COLORS[version.status] || 'neutral' : 'neutral'
}

function when(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString()
}

function displayValue(value: unknown): string {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

async function load() {
  if (!versionId.value) return
  loading.value = true
  pageErrors.value = []
  try {
    const [version, events] = await Promise.all([
      config.loadConfigurationVersion(versionId.value),
      config.loadConfigurationActivationHistory({ versionId: versionId.value, pageSize: 50 }),
    ])
    detail.value = version
    name.value = version.changeNote || ''
    history.value = events.items
    notFound.value = false
    if (route.query.action === 'rollback' && version.status !== 'DRAFT') requestRollback()
  }
  catch (error) {
    notFound.value = true
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
  finally {
    loading.value = false
  }
}

async function refreshAll() {
  await load()
  await Promise.all([
    config.loadActiveConfigurationVersion(),
    config.loadConfigurationPreview(),
  ]).catch(() => {})
}

async function save() {
  if (!detail.value || !canEdit.value) return
  validation.reset()
  const note = name.value.trim()
  if (!note) {
    validation.setFieldError('changeNote', validation.message({ code: 'required' }, 'Name'))
    void validation.focusFirstInvalid()
    return
  }
  try {
    const updated = await config.updateConfigurationVersion(detail.value.id, note)
    detail.value = { ...detail.value, ...updated }
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    validation.applyServerError(error)
    void validation.focusFirstInvalid()
  }
}

async function publish() {
  if (!detail.value) return
  const accepted = await confirm({
    kind: 'generic',
    title: `Publish v${detail.value.versionNo}?`,
    description: 'New Service Orders will use this configuration. Existing Service Orders keep the version they were captured under.',
    confirmLabel: 'Publish',
  })
  if (!accepted) return
  pageErrors.value = []
  try {
    await config.activateConfiguration(detail.value.id)
    await refreshAll()
    toast.add({ title: `v${detail.value?.versionNo} is now published`, color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

async function remove() {
  if (!detail.value) return
  const accepted = await confirm({
    kind: 'delete',
    count: 1,
    title: `Delete draft v${detail.value.versionNo}?`,
    description: 'Only an unpublished draft can be deleted. Published and retired versions always keep their history.',
    confirmLabel: t('actions.delete'),
  })
  if (!accepted) return
  pageErrors.value = []
  try {
    await config.deleteConfigurationVersion(detail.value.id)
    toast.add({ title: t('actions.delete'), color: 'success' })
    await navigateTo('/configuration/versions')
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

function requestRollback() {
  if (!detail.value) return
  rollbackReason.value = ''
  rollbackError.value = ''
  rollbackOpen.value = true
}

async function submitRollback() {
  if (!detail.value || rollingBack.value) return
  const reason = rollbackReason.value.trim()
  if (!reason) {
    rollbackError.value = 'A rollback reason is required.'
    return
  }
  rollbackError.value = ''
  rollingBack.value = true
  pageErrors.value = []
  try {
    const rolled = await config.rollbackConfiguration(detail.value.id, reason)
    rollbackOpen.value = false
    toast.add({ title: 'Rollback created a new active version', color: 'success' })
    await navigateTo(`/configuration/versions/${rolled.id}`)
  }
  catch (error) {
    const normalized = normalizeApiError(error)
    rollbackError.value = normalized.fieldErrors.reason || ''
    const message = apiErrorMessage(error, t('freight.ui.saveFailed'))
    if (!rollbackError.value) pageErrors.value = [message]
  }
  finally {
    rollingBack.value = false
  }
}

async function openCompare() {
  if (!detail.value) return
  compareOpen.value = true
  comparison.value = null
  compareFrom.value = detail.value.id
  try {
    const options = (await config.fetchConfigurationVersionOptions()).items
    compareOptions.value = options
    const preferred = options.find(item => item.id === activeId.value && item.id !== detail.value?.id)
      || options.find(item => item.id !== detail.value?.id)
    compareTo.value = preferred?.id || detail.value.id
    await runCompare()
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
    compareOpen.value = false
  }
}

async function runCompare() {
  if (!compareFrom.value || !compareTo.value) return
  comparing.value = true
  comparison.value = null
  try {
    comparison.value = await config.compareConfigurationVersions(compareFrom.value, compareTo.value)
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
  finally {
    comparing.value = false
  }
}

watch(versionId, () => { void load() }, { immediate: true })
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      show-list-nav
      list-to="/configuration/versions"
      :refreshing="loading"
      :show-save="canEdit"
      :save-label="t('freight.ui.save')"
      :saving="saving"
      show-cancel
      cancel-to="/configuration/versions"
      @refresh="refreshAll"
      @save="save"
    >
      <template #default>
        <UButton
          v-if="canPublishVersion"
          color="primary"
          size="sm"
          icon="i-lucide-check-circle-2"
          :loading="saving"
          @click="publish"
        >
          Publish
        </UButton>
        <UButton
          v-if="canRollbackVersion"
          color="warning"
          variant="soft"
          size="sm"
          icon="i-lucide-undo-2"
          :disabled="saving"
          @click="requestRollback"
        >
          Rollback
        </UButton>
        <UButton
          v-if="canCompare"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-git-compare"
          :disabled="saving"
          @click="openCompare"
        >
          Compare
        </UButton>
        <UButton
          v-if="canDelete"
          color="error"
          variant="soft"
          size="sm"
          icon="i-lucide-trash-2"
          :disabled="saving"
          @click="remove"
        >
          {{ t('actions.delete') }}
        </UButton>
      </template>
    </LayoutAppHeaderPageActions>

    <div class="min-h-0 flex-1 overflow-y-auto p-4">
      <div v-if="notFound" class="mx-auto w-[95%] max-w-[1800px]">
        <UEmpty
          variant="naked"
          icon="i-lucide-file-question"
          title="Configuration version not found"
          description="The version may have been removed, or the link is incorrect."
          class="py-16"
        />
      </div>

      <div v-else class="mx-auto w-[95%] max-w-[1800px] space-y-4">
        <CommonAppFormErrorSummary :form-errors="[...pageErrors, ...validation.formErrors.value]" />

        <div v-if="loading && !detail" class="space-y-2">
          <USkeleton v-for="index in 8" :key="index" class="h-9 w-full" />
        </div>

        <template v-else-if="detail">
          <UCard>
            <template #header>
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 class="text-base font-semibold">v{{ detail.versionNo }}</h2>
                  <p class="text-sm text-muted">{{ detail.changeNote || 'No name' }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <UBadge v-if="isActive" color="success" variant="subtle">Active</UBadge>
                  <UBadge :color="statusColor(detail)" variant="subtle">{{ detail.status }}</UBadge>
                </div>
              </div>
            </template>

            <div class="space-y-5">
              <UFormField
                label="Name"
                required
                :error="validation.fieldErrors.value.changeNote"
                data-field-key="changeNote"
              >
                <UInput
                  v-model="name"
                  :readonly="!canEdit"
                  :disabled="!canEdit"
                  :placeholder="t('freight.configVersions.changeNotePlaceholder')"
                  class="w-full"
                  maxlength="2000"
                  @update:model-value="validation.clearFieldError('changeNote')"
                  @keyup.enter="save"
                />
              </UFormField>

              <UFormField label="Description">
                <div class="rounded-md border border-default bg-elevated/40 px-3 py-2 text-sm">
                  <p>{{ detail.tabCount }} tabs · {{ detail.groupCount ?? groupCount }} groups · {{ detail.attributeCount ?? fieldCount }} fields</p>
                  <p class="text-muted">
                    {{ isImmutable ? 'Published and retired snapshots are immutable. Use Rollback to create a new version from this one.' : 'Drafts can be renamed and discarded before they are published.' }}
                  </p>
                </div>
              </UFormField>

              <div class="grid gap-3 sm:grid-cols-2">
                <div><p class="text-xs uppercase text-muted">Status</p><p class="text-sm">{{ detail.status }}</p></div>
                <div><p class="text-xs uppercase text-muted">Origin</p><p class="text-sm">{{ detail.origin || 'PUBLISH' }}</p></div>
                <div><p class="text-xs uppercase text-muted">Created By</p><p class="text-sm">{{ detail.publishedBy || detail.activatedBy || '—' }}</p></div>
                <div><p class="text-xs uppercase text-muted">Created At</p><p class="text-sm">{{ when(detail.createdAt) }}</p></div>
                <div><p class="text-xs uppercase text-muted">Published By</p><p class="text-sm">{{ detail.publishedBy || '—' }}</p></div>
                <div><p class="text-xs uppercase text-muted">Published At</p><p class="text-sm">{{ when(detail.publishedAt) }}</p></div>
                <div><p class="text-xs uppercase text-muted">Activated By</p><p class="text-sm">{{ detail.activatedBy || '—' }} · {{ when(detail.activatedAt) }}</p></div>
                <div><p class="text-xs uppercase text-muted">Source Version</p><p class="text-sm">{{ detail.sourceVersionNo ? `v${detail.sourceVersionNo}` : '—' }}</p></div>
                <div><p class="text-xs uppercase text-muted">Tabs / Groups / Fields</p><p class="text-sm">{{ detail.tabCount }} / {{ detail.groupCount ?? groupCount }} / {{ detail.attributeCount ?? fieldCount }}</p></div>
                <div><p class="text-xs uppercase text-muted">Snapshot Schema</p><p class="text-sm">v{{ detail.snapshotSchemaVersion ?? 1 }}</p></div>
                <div class="sm:col-span-2"><p class="text-xs uppercase text-muted">Content Hash</p><p class="break-all font-mono text-xs">{{ detail.contentHash || '—' }}</p></div>
              </div>
            </div>
          </UCard>

          <ConfigurationSnapshotPreview
            :tabs="previewTabs"
            :trade-directions="detail?.tradeDirections"
            description="The exact tabs, groups and fields captured by this version."
            empty-text="This version contains no tabs."
          />

          <UCard>
            <template #header>
              <h2 class="text-base font-semibold">Activation history</h2>
            </template>
            <div v-if="history.length" class="divide-y rounded-md border border-default">
              <div v-for="event in history" :key="event.id" class="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
                <span class="font-medium">{{ event.action }}</span>
                <span class="text-muted">{{ event.user }} · {{ when(event.occurredAt) }}</span>
                <span v-if="event.reason" class="w-full text-xs text-muted">{{ event.reason }}</span>
              </div>
            </div>
            <p v-else class="text-sm text-muted">No lifecycle events recorded.</p>
          </UCard>
        </template>
      </div>
    </div>

    <UModal v-model:open="rollbackOpen" title="Roll back configuration">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="text-base font-semibold">Roll back to {{ detail ? `v${detail.versionNo}` : '' }}</h3>
            <p class="text-sm text-muted">
              This creates a new version from that snapshot. Existing versions and Service Orders are preserved.
            </p>
          </template>

          <UFormField label="Rollback reason" required :error="rollbackError">
            <UTextarea
              v-model="rollbackReason"
              :rows="3"
              autoresize
              placeholder="Why is this version being restored?"
              class="w-full"
              @update:model-value="rollbackError = ''"
            />
          </UFormField>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                :disabled="rollingBack"
                @click="rollbackOpen = false"
              >
                Cancel
              </UButton>
              <UButton
                color="error"
                icon="i-lucide-undo-2"
                :loading="rollingBack"
                :disabled="!rollbackReason.trim()"
                @click="submitRollback"
              >
                Roll Back
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="compareOpen" title="Compare configuration versions" :ui="{ content: 'max-w-5xl' }">
      <template #content>
        <UCard class="max-h-[85vh] overflow-y-auto">
          <template #header>
            <h3 class="text-base font-semibold">Compare Versions</h3>
            <p class="text-sm text-muted">Objects are matched by stable id, not array position.</p>
          </template>

          <div class="space-y-4">
            <div class="grid gap-3 sm:grid-cols-2">
              <UFormField label="From version">
                <USelect
                  v-model="compareFrom"
                  :items="compareOptions.map(item => ({ label: `v${item.versionNo} · ${item.changeNote || item.status}`, value: item.id }))"
                  class="w-full"
                  @update:model-value="runCompare"
                />
              </UFormField>
              <UFormField label="To version">
                <USelect
                  v-model="compareTo"
                  :items="compareOptions.map(item => ({ label: `v${item.versionNo} · ${item.changeNote || item.status}`, value: item.id }))"
                  class="w-full"
                  @update:model-value="runCompare"
                />
              </UFormField>
            </div>

            <div v-if="comparing" class="space-y-2">
              <USkeleton v-for="index in 5" :key="index" class="h-8 w-full" />
            </div>
            <div v-else-if="comparison" class="space-y-4">
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div v-for="(count, key) in comparison.changes.summary" :key="key" class="rounded-md border border-default p-2">
                  <p class="text-[11px] uppercase text-muted">{{ String(key).replace(/([A-Z])/g, ' $1') }}</p>
                  <p class="text-lg font-semibold tabular-nums">{{ count }}</p>
                </div>
              </div>
              <UAlert
                v-if="comparison.changes.unchanged"
                color="info"
                variant="subtle"
                description="The two snapshots are structurally identical."
              />

              <section
                v-for="section in [
                  { title: 'Tabs', entries: [
                    ...comparison.changes.tabs.added.map(item => ({ ...item, kind: 'Added' })),
                    ...comparison.changes.tabs.removed.map(item => ({ ...item, kind: 'Removed' })),
                    ...comparison.changes.tabs.renamed.map(item => ({ ...item, kind: 'Renamed' })),
                  ] },
                  { title: 'Groups', entries: [
                    ...comparison.changes.groups.added.map(item => ({ ...item, kind: 'Added' })),
                    ...comparison.changes.groups.removed.map(item => ({ ...item, kind: 'Removed' })),
                    ...comparison.changes.groups.renamed.map(item => ({ ...item, kind: 'Renamed' })),
                  ] },
                  { title: 'Attributes', entries: [
                    ...comparison.changes.attributes.added.map(item => ({ ...item, kind: 'Added' })),
                    ...comparison.changes.attributes.removed.map(item => ({ ...item, kind: 'Removed' })),
                    ...comparison.changes.attributes.renamed.map(item => ({ ...item, kind: 'Renamed' })),
                    ...comparison.changes.attributes.changedFieldTypes.map(item => ({ ...item, kind: 'Field type' })),
                    ...comparison.changes.attributes.changedRequiredRules.map(item => ({ ...item, kind: 'Required' })),
                  ] },
                  { title: 'Display and layout', entries: [
                    ...comparison.changes.layouts.changedDisplayModes.map(item => ({ ...item, kind: 'Display mode' })),
                    ...comparison.changes.layouts.changedLayouts.map(item => ({ ...item, kind: 'Layout' })),
                    ...comparison.changes.ordering.map(item => ({ ...item, kind: 'Group order', label: item.tab })),
                  ] },
                ]"
                :key="section.title"
              >
                <h4 class="mb-1 text-sm font-semibold">{{ section.title }}</h4>
                <div v-if="section.entries.length" class="divide-y rounded-md border border-default">
                  <div v-for="(entry, index) in section.entries" :key="`${section.title}-${index}`" class="flex flex-wrap items-center justify-between gap-2 p-2 text-sm">
                    <span class="font-medium">{{ entry.label || entry.code || entry.id || entry.tab }}</span>
                    <span class="text-xs text-muted">{{ entry.kind }}<template v-if="entry.before !== undefined || entry.after !== undefined">: {{ displayValue(entry.before) }} → {{ displayValue(entry.after) }}</template></span>
                  </div>
                </div>
                <p v-else class="text-sm text-muted">No changes.</p>
              </section>
            </div>
          </div>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
