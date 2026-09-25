<script setup lang="ts">
import type { AppConfig } from '~/types/docetra/settings'
import type { ConnectionStatusFieldValue } from '~/types/docetra/common'
import { systemSettingsTabs } from '~/config/settings-schemas'
import { useSettingsRepositories } from '~/repositories'
import { useConfirm } from '~/composables/common/useConfirm'
import { useSetup } from '~/composables/auth/useSetup'
import { useAppPageTitle } from '~/composables/layout/useAppPageTitle'
import { getByPath, setByPath } from '~/utils/object-path'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const { appConfig, backup } = useSettingsRepositories()
const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
const setup = useSetup()
const canEdit = computed(() => auth.canAccessPage('settings.app_config.edit'))
const canConfigure = computed(() => auth.canAccessPage('settings.app_config.configure'))
const canReset = computed(() => auth.canAccessPage('settings.manage'))
const canManageBackup = computed(() => auth.canAccessPage('backup.manage'))
const appLocalization = useAppLocalization()

const runningBackup = ref(false)
const testingBackup = ref(false)
const restoringBackup = ref(false)
const restoreOpen = ref(false)
const restorePhrase = ref('')

async function runBackup() {
  if (runningBackup.value) return
  runningBackup.value = true
  try {
    if (model.value) await appConfig.update(model.value)
    const run = await backup.run()
    toast.add({ title: t('docetra.settings.backup.runStarted', { id: run.id }), color: 'success' })
  }
  catch (error) {
    const message = error instanceof Error ? error.message : ''
    toast.add({ title: message || t('docetra.settings.backup.runFailed'), color: 'error' })
  }
  finally {
    runningBackup.value = false
  }
}

async function testBackupConnection() {
  if (testingBackup.value) return
  testingBackup.value = true
  try {
    if (model.value) await appConfig.update(model.value)
    const result = await backup.testConnection()
    toast.add({
      title: result.message,
      color: result.status === 'connected' ? 'success' : 'error',
    })
  }
  catch (error) {
    const message = error instanceof Error ? error.message : ''
    toast.add({ title: message || t('docetra.settings.backup.testFailed'), color: 'error' })
  }
  finally {
    testingBackup.value = false
  }
}

async function submitRestore() {
  if (restorePhrase.value.trim().toUpperCase() !== 'RESTORE' || restoringBackup.value) return
  restoringBackup.value = true
  try {
    const result = await backup.restore('RESTORE')
    restoreOpen.value = false
    restorePhrase.value = ''
    toast.add({
      title: t('docetra.settings.backup.restoreDone', { restored: result.restored }),
      color: 'success',
    })
    await load()
  }
  catch (error) {
    const message = error instanceof Error ? error.message : ''
    toast.add({ title: message || t('docetra.settings.backup.restoreFailed'), color: 'error' })
  }
  finally {
    restoringBackup.value = false
  }
}

const resetOpen = ref(false)
const resetPhrase = ref('')
const resetting = ref(false)

async function submitReset() {
  if (resetPhrase.value.trim().toUpperCase() !== 'RESET' || resetting.value) return
  resetting.value = true
  try {
    await appConfig.resetData('RESET')
    resetOpen.value = false
    resetPhrase.value = ''
    auth.clearSession()
    await setup.refresh(true)
    toast.add({ title: t('docetra.settings.resetDataDone'), color: 'success' })
    await navigateTo('/setup', { replace: true })
  }
  catch (error) {
    const message = error instanceof Error ? error.message : ''
    toast.add({ title: message || t('docetra.settings.resetDataFailed'), color: 'error' })
  }
  finally {
    resetting.value = false
  }
}

const pending = ref(true)
const saving = ref(false)
const testingEmail = ref(false)
const testingTelegram = ref(false)
const activeTab = ref('localization')
const model = ref<AppConfig | null>(null)

async function load() {
  pending.value = true
  try {
    model.value = await appConfig.get()
  }
  catch (e) {
    toast.add({ title: e instanceof Error ? e.message : t('docetra.common.loadFailed'), color: 'error' })
  }
  finally {
    pending.value = false
  }
}

function fieldValue(key: string): unknown {
  if (!model.value) return undefined

  if (key === '__emailConnection') {
    const value: ConnectionStatusFieldValue = {
      status: model.value.email.connectionStatus,
      message: model.value.email.lastTestMessage,
      lastTestedAt: model.value.email.lastTestedAt,
    }
    return value
  }

  if (key === '__telegramConnection') {
    const value: ConnectionStatusFieldValue = {
      status: model.value.telegram.connectionStatus,
      message: model.value.telegram.lastTestMessage,
      lastTestedAt: model.value.telegram.lastTestedAt,
      details: model.value.telegram.botUsername
        ? [{ label: t('docetra.settings.botUsername'), value: model.value.telegram.botUsername }]
        : [],
    }
    return value
  }

  if (key === '__securityAlert') return null

  // Select options use string values; coerce number fields for USelect match.
  if (key === 'general.defaultPageSize' || key === 'system.paginationDefault' || key === 'backup.intervalHours') {
    const raw = getByPath(model.value, key)
    return raw == null || raw === '' ? undefined : String(raw)
  }

  return getByPath(model.value, key)
}

async function setFieldValue(key: string, value: unknown) {
  if (!model.value) return

  if (key === '__emailConnection' || key === '__telegramConnection' || key === '__securityAlert') {
    return
  }

  if (key === 'system.maintenanceMode' || key === 'system.readOnlyMode') {
    if (value === true) {
      const ok = await confirm({
        kind: 'update',
        titleKey: 'docetra.settings.confirmModeTitle',
        descriptionKey: 'docetra.settings.confirmModeHelp',
        confirmColor: 'warning',
      })
      if (!ok) return
    }
    setByPath(model.value as unknown as Record<string, unknown>, key, value)
    return
  }

  if (key === 'general.defaultPageSize' || key === 'system.paginationDefault' || key === 'backup.intervalHours') {
    const n = Number(value)
    const fallback = key === 'backup.intervalHours' ? 24 : 20
    setByPath(model.value as unknown as Record<string, unknown>, key, Number.isFinite(n) ? n : fallback)
    return
  }

  setByPath(model.value as unknown as Record<string, unknown>, key, value)
}

async function save() {
  if (!model.value) return
  saving.value = true
  try {
    model.value = await appConfig.update(model.value)
    appLocalization.apply(model.value.localization)
    usePreferencesStore().syncLocaleWithConfig()
    toast.add({ title: t('docetra.common.saved'), color: 'success' })
  }
  catch (e) {
    toast.add({ title: e instanceof Error ? e.message : t('docetra.common.saveFailed'), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

async function testEmail() {
  testingEmail.value = true
  try {
    if (model.value) await appConfig.update({ email: model.value.email })
    const result = await appConfig.testEmailConnection()
    model.value = await appConfig.get()
    toast.add({
      title: result.message,
      color: result.status === 'connected' ? 'success' : 'error',
    })
  }
  finally {
    testingEmail.value = false
  }
}

async function testTelegram() {
  testingTelegram.value = true
  try {
    if (model.value) await appConfig.update({ telegram: model.value.telegram })
    const result = await appConfig.testTelegramConnection()
    model.value = await appConfig.get()
    toast.add({
      title: result.message,
      color: result.status === 'connected' ? 'success' : 'error',
    })
  }
  finally {
    testingTelegram.value = false
  }
}

onMounted(() => void load())
useAppPageTitle(() => t('freight.pages.settings'))
</script>

<template>
  <DocumentAppDocumentPage
    v-model:active-tab="activeTab"
    :tabs="systemSettingsTabs"
    :field-value="fieldValue"
    :set-field-value="setFieldValue"
    :pending="pending || !model"
    :saving="saving"
    :read-only="!canEdit"
    :can-save="canEdit"
    :show-comments="false"
    :show-list-nav="false"
    content-wide
    @save="save"
    @refresh="load"
  >
    <template #actions>
      <CommonAppConnectionTestButton
        v-if="activeTab === 'email' && canConfigure"
        :loading="testingEmail"
        @click="testEmail"
      />
      <CommonAppConnectionTestButton
        v-if="activeTab === 'telegram' && canConfigure"
        :loading="testingTelegram"
        @click="testTelegram"
      />
      <CommonAppConnectionTestButton
        v-if="activeTab === 'backup' && canManageBackup"
        :loading="testingBackup"
        @click="testBackupConnection"
      />
      <UButton
        v-if="activeTab === 'backup' && canManageBackup"
        color="primary"
        variant="soft"
        size="sm"
        icon="i-lucide-play"
        :loading="runningBackup"
        :label="t('docetra.settings.backup.runNow')"
        @click="runBackup"
      />
      <UButton
        v-if="activeTab === 'backup' && canReset"
        color="warning"
        variant="soft"
        size="sm"
        icon="i-lucide-history"
        :label="t('docetra.settings.backup.restore')"
        @click="restoreOpen = true"
      />
      <UButton
        v-if="canReset"
        color="error"
        variant="soft"
        size="sm"
        icon="i-lucide-trash-2"
        :label="t('docetra.settings.resetData')"
        @click="resetOpen = true"
      />
    </template>
  </DocumentAppDocumentPage>

  <UModal
    v-model:open="resetOpen"
    :title="t('docetra.settings.resetDataConfirmTitle')"
    :dismissible="!resetting"
  >
    <template #body>
      <div class="space-y-3">
        <UAlert
          color="error"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('docetra.settings.resetDataHint')"
        />
        <p class="text-sm text-muted">{{ t('docetra.settings.resetDataConfirmHelp') }}</p>
        <UInput
          v-model="resetPhrase"
          :placeholder="t('docetra.settings.resetDataPlaceholder')"
          class="w-full"
          autofocus
        />
      </div>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('docetra.common.cancel')"
          :disabled="resetting"
          @click="resetOpen = false; resetPhrase = ''"
        />
        <UButton
          color="error"
          :label="t('docetra.settings.resetDataConfirm')"
          :loading="resetting"
          :disabled="resetPhrase.trim().toUpperCase() !== 'RESET'"
          @click="submitReset"
        />
      </div>
    </template>
  </UModal>

  <UModal
    v-model:open="restoreOpen"
    :title="t('docetra.settings.backup.restoreConfirmTitle')"
    :dismissible="!restoringBackup"
  >
    <template #body>
      <div class="space-y-3">
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('docetra.settings.backup.restoreHint')"
        />
        <p class="text-sm text-muted">{{ t('docetra.settings.backup.restoreConfirmHelp') }}</p>
        <UInput
          v-model="restorePhrase"
          :placeholder="t('docetra.settings.backup.restorePlaceholder')"
          class="w-full"
          autofocus
        />
      </div>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('docetra.common.cancel')"
          :disabled="restoringBackup"
          @click="restoreOpen = false; restorePhrase = ''"
        />
        <UButton
          color="warning"
          :label="t('docetra.settings.backup.restoreConfirm')"
          :loading="restoringBackup"
          :disabled="restorePhrase.trim().toUpperCase() !== 'RESTORE'"
          @click="submitRestore"
        />
      </div>
    </template>
  </UModal>
</template>
