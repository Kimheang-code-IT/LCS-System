<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { AppConfig } from '~/types/settings'
import type { ConnectionStatusFieldValue } from '~/types/common'
import { systemSettingsTabs } from '~/config/settings-schemas'
import { useSettingsRepositories } from '~/repositories'
import { useConfirm } from '~/composables/common/useConfirm'
import { useAppPageTitle } from '~/composables/layout/useAppPageTitle'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { validateDocumentFields } from '~/utils/validation/record-validation'
import type { FieldRule, ValidationFailure } from '~/utils/validation/field-rules'
import type { FreightField } from '~/config/freight-modules'
import { getByPath, setByPath } from '~/utils/object-path'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const { appConfig, backup } = useSettingsRepositories()
const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
const freight = useFreightStore()
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
/** Page-level refusals (bad credentials, network) — rendered, never toasted. */
const pageErrors = ref<string[]>([])

/**
 * Shared validation for the settings form. Keys are dotted config paths
 * (`email.smtp.host`), so a backend error maps straight onto its input.
 */
const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  order: () => systemSettingsTabs
    .flatMap(tab => tab.sections)
    .flatMap(section => section.fields.map(field => field.key)),
  reveal: (key) => {
    const tab = systemSettingsTabs.find(item =>
      item.sections.some(section => section.fields.some(field => field.key === key)),
    )
    if (!tab || activeTab.value === tab.id) return Boolean(tab)
    activeTab.value = tab.id
    return true
  },
})

async function runBackup() {
  if (runningBackup.value) return
  runningBackup.value = true
  pageErrors.value = []
  try {
    if (model.value) await appConfig.update(model.value)
    const run = await backup.run()
    toast.add({ title: t('lcs.settings.backup.runStarted', { id: run.id }), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('lcs.settings.backup.runFailed'))]
  }
  finally {
    runningBackup.value = false
  }
}

async function testBackupConnection() {
  if (testingBackup.value) return
  testingBackup.value = true
  pageErrors.value = []
  try {
    if (model.value) await appConfig.update(model.value)
    const result = await backup.testConnection()
    if (result.status === 'connected') {
      toast.add({ title: result.message, color: 'success' })
    }
    else {
      pageErrors.value = [result.message || t('lcs.settings.backup.testFailed')]
    }
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('lcs.settings.backup.testFailed'))]
  }
  finally {
    testingBackup.value = false
  }
}

async function submitRestore() {
  if (restorePhrase.value.trim().toUpperCase() !== 'RESTORE' || restoringBackup.value) return
  restoringBackup.value = true
  pageErrors.value = []
  try {
    const result = await backup.restore('RESTORE')
    restoreOpen.value = false
    restorePhrase.value = ''
    toast.add({
      title: t('lcs.settings.backup.restoreDone', { restored: result.restored }),
      color: 'success',
    })
    await load()
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('lcs.settings.backup.restoreFailed'))]
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
  pageErrors.value = []
  try {
    await appConfig.resetData('RESET')
    resetOpen.value = false
    resetPhrase.value = ''
    freight.reload()
    await load()
    toast.add({ title: t('lcs.settings.resetDataDone'), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('lcs.settings.resetDataFailed'))]
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
    pageErrors.value = [apiErrorMessage(e, t('lcs.common.loadFailed'))]
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
        ? [{ label: t('lcs.settings.botUsername'), value: model.value.telegram.botUsername }]
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
        titleKey: 'lcs.settings.confirmModeTitle',
        descriptionKey: 'lcs.settings.confirmModeHelp',
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

/** Every editable settings field, in tab order (read-only mirrors excluded). */
function editableSettingsFields() {
  return systemSettingsTabs
    .flatMap(tab => tab.sections)
    .flatMap(section => section.fields)
    .filter(field => !field.readOnly && !field.type?.includes('connection') && field.type !== 'alert')
}

function settingsLabel(key: string) {
  const field = editableSettingsFields().find(item => item.key === key)
  return field?.labelKey ? t(field.labelKey) : key
}

/**
 * Client-side rules for the settings form.
 *
 * The backend re-validates all of this; checking here keeps a typo on the
 * input that caused it instead of sending a request that can only fail.
 * Conditional requirements are expressed as rule overrides because a blank
 * SMTP host is fine while email is disabled and required the moment it is on.
 */
function settingsRules(): Record<string, FieldRule> {
  const emailEnabled = Boolean(model.value?.email.enabled)
  const telegramEnabled = Boolean(model.value?.telegram.enabled)
  const backupEnabled = Boolean(model.value?.backup.enabled)
  return {
    'general.maxUploadSizeMb': { number: true, integer: true, min: 1, max: 100 },
    'email.smtpHost': { required: emailEnabled, maxLength: 255 },
    'email.smtpPort': { number: true, integer: true, min: 1, max: 65535, required: emailEnabled },
    'email.username': { maxLength: 255 },
    'telegram.botDisplayName': { maxLength: 255 },
    'telegram.botUsername': { maxLength: 255 },
    'telegram.botToken': { required: telegramEnabled, maxLength: 512 },
    'notifications.deliveryRetries': { number: true, integer: true, min: 0, max: 10 },
    'security.sessionTimeoutMinutes': { number: true, integer: true, min: 1, max: 1440 },
    'security.maxLoginAttempts': { number: true, integer: true, min: 1, max: 100 },
    'security.accountLockMinutes': { number: true, integer: true, min: 1, max: 1440 },
    'security.passwordExpiryDays': { number: true, integer: true, min: 0, max: 3650 },
    'backup.intervalHours': { number: true, integer: true, min: 1, max: 168 },
    'backup.r2AccountId': { required: backupEnabled, maxLength: 128 },
    'backup.r2AccessKeyId': { required: backupEnabled, maxLength: 255 },
    'backup.r2SecretAccessKey': { required: backupEnabled, maxLength: 512 },
    'backup.r2BucketName': { required: backupEnabled, maxLength: 255 },
    'backup.r2Endpoint': { required: backupEnabled, url: true, maxLength: 500 },
    'backup.r2Prefix': { maxLength: 255 },
  }
}

function collectSettingsFailures(keys?: string[]): ValidationFailure[] {
  const fields = editableSettingsFields()
    .filter(field => !keys || keys.includes(field.key))
    .map(field => ({
      key: field.key,
      type: field.type === 'text' ? 'text' : field.type,
      required: Boolean(field.required),
      rule: settingsRules()[field.key],
    }))
  return validateDocumentFields({
    fields: fields as unknown as FreightField[],
    model: (model.value || {}) as unknown as Record<string, unknown>,
    isCreate: true,
    label: settingsLabel,
  })
}

function validateSettingsField(key: string) {
  const failures = collectSettingsFailures([key])
  validation.clearFieldError(key)
  const failure = failures.find(item => item.key === key)
  if (failure) validation.setFieldError(key, validation.message(failure, settingsLabel(key)))
}

async function save() {
  if (!model.value || saving.value) return
  saving.value = true
  validation.submitting.value = true
  validation.reset()
  try {
    const failures = collectSettingsFailures()
    if (failures.length) {
      validation.applyFailures(failures)
      await validation.focusFirstInvalid()
      return
    }
    model.value = await appConfig.update(model.value)
    appLocalization.apply(model.value.localization)
    usePreferencesStore().syncLocaleWithConfig()
    toast.add({ title: t('lcs.common.saved'), color: 'success' })
  }
  catch (error) {
    // Field-addressable refusals land on their input; anything else becomes a
    // page-level message and the form keeps the values the user entered.
    validation.applyServerError(error)
    await validation.focusFirstInvalid()
  }
  finally {
    saving.value = false
    validation.submitting.value = false
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

const moreItems = computed<DropdownMenuItem[][]>(() => {
  const actions: DropdownMenuItem[] = []
  const danger: DropdownMenuItem[] = []

  if (activeTab.value === 'email' && canConfigure.value) {
    actions.push({
      label: t('lcs.connection.test'),
      icon: 'i-lucide-plug-zap',
      disabled: testingEmail.value,
      onSelect: () => { void testEmail() },
    })
  }
  if (activeTab.value === 'telegram' && canConfigure.value) {
    actions.push({
      label: t('lcs.connection.test'),
      icon: 'i-lucide-plug-zap',
      disabled: testingTelegram.value,
      onSelect: () => { void testTelegram() },
    })
  }
  if (activeTab.value === 'backup' && canManageBackup.value) {
    actions.push({
      label: t('lcs.connection.test'),
      icon: 'i-lucide-plug-zap',
      disabled: testingBackup.value,
      onSelect: () => { void testBackupConnection() },
    })
    actions.push({
      label: t('lcs.settings.backup.runNow'),
      icon: 'i-lucide-play',
      disabled: runningBackup.value,
      onSelect: () => { void runBackup() },
    })
  }
  if (activeTab.value === 'backup' && canReset.value) {
    actions.push({
      label: t('lcs.settings.backup.restore'),
      icon: 'i-lucide-history',
      onSelect: () => { restoreOpen.value = true },
    })
  }
  if (canReset.value) {
    danger.push({
      label: t('lcs.settings.resetData'),
      icon: 'i-lucide-trash-2',
      color: 'error',
      onSelect: () => { resetOpen.value = true },
    })
  }

  return [actions, danger].filter(group => group.length)
})

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
    :more-items="moreItems"
    :field-errors="validation.fieldErrors.value"
    :form-errors="[...validation.formErrors.value, ...pageErrors]"
    :on-field-edit="validation.clearFieldError"
    :on-field-blur="validateSettingsField"
    content-wide
    @save="save"
    @refresh="load"
  />

  <UModal
    v-model:open="resetOpen"
    :title="t('lcs.settings.resetDataConfirmTitle')"
    :dismissible="!resetting"
  >
    <template #body>
      <div class="space-y-3">
        <UAlert
          color="error"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('lcs.settings.resetDataHint')"
        />
        <p class="text-sm text-muted">{{ t('lcs.settings.resetDataConfirmHelp') }}</p>
        <UInput
          v-model="resetPhrase"
          :placeholder="t('lcs.settings.resetDataPlaceholder')"
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
          :label="t('lcs.common.cancel')"
          :disabled="resetting"
          @click="resetOpen = false; resetPhrase = ''"
        />
        <UButton
          color="error"
          :label="t('lcs.settings.resetDataConfirm')"
          :loading="resetting"
          :disabled="resetPhrase.trim().toUpperCase() !== 'RESET'"
          @click="submitReset"
        />
      </div>
    </template>
  </UModal>

  <UModal
    v-model:open="restoreOpen"
    :title="t('lcs.settings.backup.restoreConfirmTitle')"
    :dismissible="!restoringBackup"
  >
    <template #body>
      <div class="space-y-3">
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('lcs.settings.backup.restoreHint')"
        />
        <p class="text-sm text-muted">{{ t('lcs.settings.backup.restoreConfirmHelp') }}</p>
        <UInput
          v-model="restorePhrase"
          :placeholder="t('lcs.settings.backup.restorePlaceholder')"
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
          :label="t('lcs.common.cancel')"
          :disabled="restoringBackup"
          @click="restoreOpen = false; restorePhrase = ''"
        />
        <UButton
          color="warning"
          :label="t('lcs.settings.backup.restoreConfirm')"
          :loading="restoringBackup"
          :disabled="restorePhrase.trim().toUpperCase() !== 'RESTORE'"
          @click="submitRestore"
        />
      </div>
    </template>
  </UModal>
</template>
