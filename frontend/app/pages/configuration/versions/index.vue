<script setup lang="ts">
/**
 * Published configuration versions.
 *
 * Tabs, groups and attributes are edited on the sibling pages. This page freezes
 * the result: a publish records exactly which tabs, groups and fields were live,
 * and every Service Order created afterwards is pinned to that version. Service
 * Orders already captured keep the version they were created under, so editing
 * the form can never change how existing data reads.
 */
import type { ConfigurationVersion } from '~/types/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'

definePageMeta({
  titleKey: 'freight.pages.configurationVersions',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const config = useComponentConfig()

const note = ref('')
const historyOpen = ref(false)
/** Page-level refusals (empty configuration, conflicting publish, network). */
const pageErrors = ref<string[]>([])

const currentVersion = computed(() =>
  config.versions.value.find(version => version.status === 'PUBLISHED') || null)
const history = computed(() =>
  config.versions.value.filter(version => version.id !== currentVersion.value?.id))
const canPublish = computed(() =>
  config.preview.value !== null && config.preview.value.tabCount > 0 && !config.preview.value.unchanged)

const STATUS_COLORS: Record<ConfigurationVersion['status'], BadgeColor> = {
  PUBLISHED: 'success',
  DRAFT: 'neutral',
  RETIRED: 'warning',
}

type BadgeColor = 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'primary' | 'secondary'

function statusColor(version: ConfigurationVersion): BadgeColor {
  return STATUS_COLORS[version.status] || 'neutral'
}

function when(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString()
}

onMounted(async () => {
  await Promise.all([config.loadConfigurationVersions(), config.loadConfigurationPreview()])
})

async function publish() {
  pageErrors.value = []
  try {
    await config.publishConfiguration(note.value.trim() || undefined)
    note.value = ''
    toast.add({ title: t('freight.configVersions.published'), color: 'success' })
  }
  catch {
    // Conflicting publishes (409) and empty configurations (422) surface the
    // backend message, which is the actionable part. Shown above the form:
    // this is a page-level refusal, not a validation error on one input.
    await config.loadConfigurationPreview()
    pageErrors.value = [config.error.value || t('freight.ui.saveFailed')]
  }
}

async function refresh() {
  await Promise.all([config.loadConfigurationVersions(), config.loadConfigurationPreview()])
}

async function retire(version: ConfigurationVersion) {
  pageErrors.value = []
  try {
    await config.retireConfiguration(version.id)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    pageErrors.value = [config.error.value || t('freight.ui.saveFailed')]
  }
}
</script>

<template>
  <div class="space-y-4 p-4">
    <CommonAppFormErrorSummary :form-errors="pageErrors" />
    <UCard>
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold">{{ t('freight.configVersions.title') }}</h2>
            <p class="text-sm text-muted">{{ t('freight.configVersions.description') }}</p>
          </div>
          <UBadge
            v-if="currentVersion"
            color="success"
            variant="subtle"
          >
            {{ t('freight.configVersions.current', { no: currentVersion.versionNo }) }}
          </UBadge>
          <UBadge
            v-else
            color="warning"
            variant="subtle"
          >
            {{ t('freight.configVersions.none') }}
          </UBadge>
        </div>
      </template>

      <div class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <p class="text-xs uppercase text-muted">{{ t('freight.configVersions.tabs') }}</p>
            <p class="text-lg font-semibold">{{ config.preview.value?.tabCount ?? 0 }}</p>
          </div>
          <div>
            <p class="text-xs uppercase text-muted">{{ t('freight.configVersions.state') }}</p>
            <p class="text-sm font-medium">
              {{ config.preview.value?.unchanged
                ? t('freight.configVersions.upToDate')
                : t('freight.configVersions.pendingChanges') }}
            </p>
          </div>
          <div>
            <p class="text-xs uppercase text-muted">{{ t('freight.configVersions.publishedAt') }}</p>
            <p class="text-sm font-medium">{{ when(currentVersion?.publishedAt) }}</p>
          </div>
        </div>

        <UAlert
          v-if="config.preview.value && config.preview.value.tabCount === 0"
          color="warning"
          variant="subtle"
          :title="t('freight.configVersions.emptyTitle')"
          :description="t('freight.configVersions.emptyDescription')"
        />

        <UAlert
          v-else-if="config.preview.value?.unchanged"
          color="info"
          variant="subtle"
          :description="t('freight.configVersions.unchangedDescription')"
        />

        <UFormField :label="t('freight.configVersions.changeNote')">
          <UInput
            v-model="note"
            :placeholder="t('freight.configVersions.changeNotePlaceholder')"
            class="w-full"
          />
        </UFormField>

        <div class="flex flex-wrap gap-2">
          <UButton
            :loading="config.saving.value"
            :disabled="!canPublish"
            icon="i-lucide-upload-cloud"
            @click="publish"
          >
            {{ t('freight.configVersions.publish') }}
          </UButton>
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-refresh-cw"
            :loading="config.loading.value"
            @click="refresh"
          >
            {{ t('actions.refresh') }}
          </UButton>
          <UButton
            v-if="history.length"
            color="neutral"
            variant="ghost"
            icon="i-lucide-history"
            @click="historyOpen = !historyOpen"
          >
            {{ t('freight.configVersions.history') }}
          </UButton>
        </div>

        <div
          v-if="historyOpen && history.length"
          class="divide-y rounded-md border"
        >
          <div
            v-for="version in history"
            :key="version.id"
            class="flex flex-wrap items-center justify-between gap-2 p-3"
          >
            <div class="flex items-center gap-2">
              <UBadge
                :color="statusColor(version)"
                variant="subtle"
                size="sm"
              >
                v{{ version.versionNo }} · {{ version.status }}
              </UBadge>
              <span class="text-sm text-muted">{{ version.changeNote || '—' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted">{{ when(version.publishedAt || version.createdAt) }}</span>
              <UButton
                v-if="version.status === 'DRAFT'"
                size="xs"
                color="neutral"
                variant="outline"
                @click="retire(version)"
              >
                {{ t('freight.configVersions.retire') }}
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
