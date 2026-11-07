<script setup lang="ts">
/**
 * Action console for the Storage & Backup tab. The page schema owns the
 * provider config fields; this panel owns the connection, backup, migration
 * and restore actions plus their live status displays.
 */
import { useStorageSettings } from '~/composables/settings/useStorageSettings'

const props = defineProps<{
  canManage: boolean
  canManageBackup: boolean
  /** Re-reads status after the page saved the config form. */
  savedAt?: number
}>()

const {
  providers, overview, pageError, busy, pendingAction, load,
  testConnection, connectGoogle, disconnectGoogle,
  backupNow, retryFailed, historyOpen, history, loadHistory,
  migrationOpen, migrationTarget, migrationDryRun, migrationPreview, migrationJob, migrationBusy,
  openMigration, previewMigration, startMigration,
  restoreOpen, restorePreview, restoreJob, openRestore, executeRestore,
} = useStorageSettings()
const { t } = useI18n()

const statusColor = (status: string | undefined) =>
  status === 'connected' ? 'success' : status === 'connection_failed' || status === 'disconnected' ? 'error' : 'neutral'

const statusLabel = (status: string | undefined) => {
  switch (status) {
    case 'connected': return 'lcs.settings.storage.statusConnected'
    case 'connection_failed': return 'lcs.settings.storage.statusFailed'
    case 'disconnected': return 'lcs.settings.storage.statusDisconnected'
    default: return 'lcs.settings.storage.statusNotConfigured'
  }
}

const formatBytes = (bytes: number) => {
  if (!bytes) return '0 KB'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * After the config form is saved the provider blocks may have changed, so the
 * status snapshot is refreshed on each save (page passes `savedAt`).
 */
watch(() => props.savedAt, () => void load())
onMounted(() => void load())
</script>

<template>
  <div class="space-y-4">
    <UAlert
      v-if="pageError"
      color="error"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="pageError"
    />
    <div class="grid gap-4 lg:grid-cols-2">
      <UCard data-field-key="storage.r2Status">
        <template #header>
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-semibold">{{ t('lcs.settings.storage.r2Section') }}</span>
            <UBadge
              :color="statusColor(providers?.r2.connectionStatus)"
              variant="soft"
              size="sm"
            >
              {{ t(statusLabel(providers?.r2.connectionStatus)) }}
            </UBadge>
          </div>
        </template>
        <p class="text-xs text-muted">
          {{ providers?.r2.lastTestMessage || t('lcs.settings.storage.noTestRun') }}
        </p>
        <p v-if="providers?.r2.lastVerifiedAt" class="text-xs text-muted">
          {{ t('lcs.settings.storage.lastVerified', { at: providers.r2.lastVerifiedAt.replace('T', ' ').slice(0, 19) }) }}
        </p>
        <UButton
          class="mt-3"
          icon="i-lucide-plug-zap"
          size="sm"
          variant="outline"
          :loading="busy"
          :disabled="!canManage"
          @click="testConnection('r2')"
        >
          {{ t('lcs.connection.test') }}
        </UButton>
      </UCard>

      <UCard data-field-key="storage.gdriveStatus">
        <template #header>
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-semibold">{{ t('lcs.settings.storage.gDriveSection') }}</span>
            <UBadge
              :color="statusColor(providers?.gdrive.connectionStatus)"
              variant="soft"
              size="sm"
            >
              {{ t(statusLabel(providers?.gdrive.connectionStatus)) }}
            </UBadge>
          </div>
        </template>
        <p class="text-xs text-muted">
          {{ providers?.gdrive.lastTestMessage || t('lcs.settings.storage.noTestRun') }}
        </p>
        <p v-if="providers?.gdrive.connectedEmail" class="text-xs text-muted">
          {{ t('lcs.settings.storage.connectedAs', { email: providers.gdrive.connectedEmail }) }}
        </p>
        <div class="mt-3 flex flex-wrap gap-2">
          <UButton
            icon="i-lucide-log-in"
            size="sm"
            :loading="busy"
            :disabled="!canManage"
            @click="connectGoogle()"
          >
            {{ t(providers?.gdrive.connectedEmail ? 'lcs.settings.storage.changeAccount' : 'lcs.settings.storage.connect') }}
          </UButton>
          <UButton
            icon="i-lucide-plug-zap"
            size="sm"
            variant="outline"
            :loading="busy"
            :disabled="!canManage"
            @click="testConnection('gdrive')"
          >
            {{ t('lcs.connection.test') }}
          </UButton>
          <UButton
            icon="i-lucide-log-out"
            size="sm"
            variant="outline"
            :loading="pendingAction"
            :disabled="!canManage || !providers?.gdrive.connectedEmail"
            @click="disconnectGoogle()"
          >
            {{ t('lcs.settings.storage.disconnect') }}
          </UButton>
        </div>
      </UCard>
    </div>

    <UCard v-if="overview" data-field-key="storage.backupOverview">
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-semibold">{{ t('lcs.settings.storage.backupSection') }}</span>
          <UBadge :color="overview.backupEnabled ? 'success' : 'neutral'" variant="soft" size="sm">
            {{ t(overview.backupEnabled ? 'lcs.settings.storage.backupOn' : 'lcs.settings.storage.backupOff') }}
          </UBadge>
        </div>
      </template>
      <dl class="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div class="flex justify-between gap-2 sm:block">
          <dt class="text-muted">{{ t('lcs.settings.storage.primaryProvider') }}</dt>
          <dd class="font-medium">{{ t('lcs.settings.storage.provider' + (overview.primaryProvider || 'Legacy')) }}</dd>
        </div>
        <div class="sm:block">
          <dt class="text-muted">{{ t('lcs.settings.storage.backupProvider') }}</dt>
          <dd class="font-medium">{{ overview.backupProvider ? t('lcs.settings.storage.provider' + overview.backupProvider) : t('lcs.settings.storage.providerDisabled') }}</dd>
        </div>
        <div class="sm:block">
          <dt class="text-muted">{{ t('lcs.settings.storage.lastBackup') }}</dt>
          <dd class="font-medium">{{ overview.lastSuccessfulBackup ? overview.lastSuccessfulBackup.slice(0, 19).replace('T', ' ') : '—' }}</dd>
        </div>
        <div class="sm:block">
          <dt class="text-muted">{{ t('lcs.settings.storage.pendingBackups') }}</dt>
          <dd class="font-medium">{{ overview.pending }}</dd>
        </div>
      </dl>
      <p v-if="overview.lastFailedBackup" class="text-xs text-error">
        {{ t('lcs.settings.storage.lastFailed', { at: overview.lastFailedBackup.slice(0, 19).replace('T', ' ') }) }}
      </p>

      <div class="mt-4 flex flex-wrap gap-2">
        <UButton
          icon="i-lucide-play"
          size="sm"
          :loading="busy"
          :disabled="!canManageBackup"
          @click="backupNow()"
        >
          {{ t('lcs.settings.storage.backupNow') }}
        </UButton>
        <UButton
          icon="i-lucide-refresh-ccw"
          variant="outline"
          size="sm"
          :loading="busy"
          :disabled="!canManageBackup"
          @click="retryFailed()"
        >
          {{ t('lcs.settings.storage.retryFailed') }}
        </UButton>
        <UButton
          icon="i-lucide-history"
          variant="outline"
          size="sm"
          :disabled="!canManageBackup || pendingAction"
          @click="historyOpen = true; void loadHistory()"
        >
          {{ t('lcs.settings.storage.viewHistory') }}
        </UButton>
        <UButton
          icon="i-lucide-undo-2"
          variant="outline"
          size="sm"
          :disabled="!canManageBackup || pendingAction"
          @click="openRestore()"
        >
          {{ t('lcs.settings.storage.restore') }}
        </UButton>
      </div>
    </UCard>

    <UCard data-field-key="storage.migration">
      <template #header>
        <span class="text-sm font-semibold">{{ t('lcs.settings.storage.migrationSection') }}</span>
      </template>
      <p class="text-sm text-muted">{{ t('lcs.settings.storage.migrationHelp') }}</p>
      <UButton
        class="mt-3"
        icon="i-lucide-arrow-right-left"
        variant="outline"
        size="sm"
        :disabled="!canManage || pendingAction"
        @click="openMigration()"
      >
        {{ t('lcs.settings.storage.openMigration') }}
      </UButton>
    </UCard>

    <!-- Backup history -->
    <UModal
      v-model:open="historyOpen"
      :title="t('lcs.settings.storage.viewHistory')"
    >
      <template #body>
        <ul v-if="history.length" class="space-y-2 text-sm">
          <li
            v-for="job in history"
            :key="job.id"
            class="flex items-center justify-between gap-2 rounded border border-default px-3 py-2"
          >
            <div class="min-w-0">
              <p class="truncate font-medium">{{ t('lcs.settings.storage.job' + job.jobType) }} → {{ t('lcs.settings.storage.provider' + job.target) }}</p>
              <p class="text-xs text-muted">{{ job.startedAt?.slice(0, 19).replace('T', ' ') || job.id }}</p>
            </div>
            <div class="text-right text-xs">
              <UBadge :color="job.status === 'COMPLETED' ? 'success' : job.status === 'FAILED' ? 'error' : 'info'" variant="soft" size="sm">
                {{ job.status }}
              </UBadge>
              <p class="text-muted">{{ job.processed }}/{{ job.total }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="text-sm text-muted">{{ t('lcs.settings.storage.noHistory') }}</p>
      </template>
      <template #footer>
        <div class="flex w-full justify-end">
          <UButton variant="ghost" color="neutral" @click="historyOpen = false">
            {{ t('lcs.common.close') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Migration -->
    <UModal
      v-model:open="migrationOpen"
      :title="t('lcs.settings.storage.migrationSection')"
    >
      <template #body>
        <div class="space-y-3">
          <p class="text-sm text-muted">{{ t('lcs.settings.storage.migrationHelp') }}</p>
          <UFormField :label="t('lcs.settings.storage.migrationTarget')">
            <USelect
              v-model="migrationTarget"
              :items="[
                { label: t('lcs.settings.storage.providerR2'), value: 'r2' },
                { label: t('lcs.settings.storage.providerGDrive'), value: 'gdrive' },
              ]"
              value-key="value"
              class="w-full"
              :disabled="migrationBusy"
            />
          </UFormField>
          <UCheckbox
            v-model="migrationDryRun"
            :label="t('lcs.settings.storage.dryRun')"
          />
          <div class="flex gap-2">
            <UButton
              variant="outline"
              size="sm"
              :loading="migrationBusy"
              :disabled="!canManage"
              @click="previewMigration(migrationTarget)"
            >
              {{ t('lcs.settings.storage.previewMigration') }}
            </UButton>
            <UButton
              icon="i-lucide-arrow-right-left"
              size="sm"
              :loading="migrationBusy"
              :disabled="!canManage"
              @click="startMigration()"
            >
              {{ migrationDryRun ? t('lcs.settings.storage.dryRunPreview') : t('lcs.settings.storage.startMigration') }}
            </UButton>
          </div>
          <div v-if="migrationPreview" class="rounded border border-default p-3 text-sm">
            <ul class="space-y-1 text-muted">
              <li>{{ t('lcs.settings.storage.previewFiles', { n: migrationPreview.files }) }}</li>
              <li>{{ t('lcs.settings.storage.previewBytes', { b: formatBytes(migrationPreview.bytes) }) }}</li>
              <li>{{ t('lcs.settings.storage.previewTarget', { n: migrationPreview.alreadyOnTarget, to: migrationPreview.toMigrate }) }}</li>
            </ul>
          </div>
          <div v-if="migrationJob" class="rounded border border-default p-3">
            <UProgress :model-value="migrationJob.progress" size="sm" />
            <p class="mt-2 text-xs text-muted">
              {{ migrationJob.message || `${migrationJob.processed}/${migrationJob.total}` }}
            </p>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end">
          <UButton
variant="ghost"
color="neutral"
:disabled="migrationBusy"
@click="migrationOpen = false">
            {{ t('lcs.common.close') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Restore -->
    <UModal
      v-model:open="restoreOpen"
      :title="t('lcs.settings.storage.restore')"
    >
      <template #body>
        <div class="space-y-3">
          <UAlert
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :description="t('lcs.settings.storage.restoreHint')"
          />
          <p v-if="restorePreview" class="text-sm text-muted">
            {{ t('lcs.settings.storage.restorePreviewInfo', {
              restorable: restorePreview.restorable,
              replicas: restorePreview.replicas,
              primary: restorePreview.primary,
            }) }}
          </p>
          <div v-if="restoreJob" class="rounded border border-default p-3">
            <UProgress :model-value="restoreJob.progress" size="sm" />
            <p class="mt-2 text-xs text-muted">
              {{ restoreJob.message || `${restoreJob.processed}/${restoreJob.total}` }}
            </p>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton variant="ghost" color="neutral" @click="restoreOpen = false">
            {{ t('lcs.common.close') }}
          </UButton>
          <UButton
            color="warning"
            :disabled="!canManageBackup || (restorePreview?.restorable ?? 0) === 0"
            :loading="busy"
            @click="executeRestore()"
          >
            {{ t('lcs.settings.storage.restoreConfirm') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
