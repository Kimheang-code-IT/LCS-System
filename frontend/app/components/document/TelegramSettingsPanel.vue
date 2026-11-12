<script setup lang="ts">
import { useSettingsRepositories } from '~/repositories'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { isValidTelegramGroupChatId } from '~/utils/validation/telegram-chat-id'
import type { TelegramConfig } from '~/types/settings'

/**
 * Settings → Telegram. Exactly two destinations as two aligned cards:
 * Client Group (Service Order notifications) and Admin Bot (system alerts to a
 * verified administrator's private chat). The shared Bot Token stays in the
 * tab's schema field above. Every control writes through the page's existing
 * Save Changes workflow — this panel has no save button of its own.
 */
const props = defineProps<{ config: TelegramConfig, canManage: boolean }>()
const emit = defineEmits<{
  refresh: [],
  'update:rules': [value: TelegramConfig['rules']],
  'update:config': [value: Partial<TelegramConfig>],
}>()
const { t } = useI18n()
const { appConfig } = useSettingsRepositories()

const pending = ref(false)
const error = ref('')
const status = ref('')

const CLIENT_EVENT_KEYS = [
  'SERVICE_ORDER_CREATED',
  'SERVICE_ORDER_UPDATED',
  'SERVICE_ORDER_STATUS_CHANGED',
  'SERVICE_ORDER_FINISHED',
  'SERVICE_ORDER_CANCELLED',
] as const
const CLIENT_EVENT_LABELS: Record<(typeof CLIENT_EVENT_KEYS)[number], string> = {
  SERVICE_ORDER_CREATED: 'telegram.eventCreated',
  SERVICE_ORDER_UPDATED: 'telegram.eventUpdated',
  SERVICE_ORDER_STATUS_CHANGED: 'telegram.eventStatusChanged',
  SERVICE_ORDER_FINISHED: 'telegram.eventFinished',
  SERVICE_ORDER_CANCELLED: 'telegram.eventCancelled',
}

/** Backend alert registry categories; recovery stays server-governed and can
 * only reach previously verified private chats, never this screen. */
const ALERT_CATEGORY_KEYS = ['security', 'backup', 'system'] as const
const alertRules = computed(() => props.config.rules ?? {})
const recipientCount = computed(() => props.config.adminRecipientCount ?? 0)
/** Telegram cannot receive /start or /verify without a running, configured consumer. */
const updatesInactive = computed(() => props.config.workerEnabled === false
  || ['disabled', 'misconfigured', 'failed'].includes(props.config.updateStatus ?? '')
  || (props.config.updateMode !== 'polling' && props.config.webhookStatus !== 'registered'))
const workerStatusText = computed(() => {
  const mode = props.config.updateMode ?? 'webhook'
  const status = props.config.updateStatus ?? 'starting'
  const error = props.config.lastError ? ` · ${props.config.lastError}` : ''
  return `${mode} · ${status}${error}`
})

function patch(value: Partial<TelegramConfig>) {
  emit('update:config', value)
}

function updateClientEvent(key: string, enabled: boolean) {
  patch({ clientEvents: { ...(props.config.clientEvents ?? {}), [key]: enabled } })
}

function updateRule(key: string, enabled: boolean) {
  const rule = alertRules.value[key]
  if (!rule) return
  emit('update:rules', { ...alertRules.value, [key]: { ...rule, enabled } })
}

function statusText(value: string | undefined): string {
  if (!value || value === 'not_tested') return t('telegram.notTested')
  if (value === 'connected') return t('telegram.connected')
  return t('telegram.sendFailed')
}

/** Testing verifies what is stored; persist only this destination's fields so a
 * half-typed value in the other card can never block the test. */
async function perform(save: Partial<TelegramConfig>, action: () => Promise<{ message: string }>) {
  if (pending.value) return
  pending.value = true
  error.value = ''
  status.value = ''
  try {
    await appConfig.update({ telegram: save })
    status.value = (await action()).message
    emit('refresh')
  }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')) }
  finally { pending.value = false }
}

async function sendTest(action: () => Promise<{ message: string }>) {
  if (pending.value) return
  pending.value = true
  error.value = ''
  status.value = ''
  try {
    status.value = (await action()).message
  }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')) }
  finally { pending.value = false }
}

/** Page Save hook: validate the client destination before the request. */
function validate(): boolean {
  if (props.config.clientEnabled && !isValidTelegramGroupChatId(props.config.clientGroupId ?? '')) {
    error.value = t('telegram.invalidClientChatId')
    return false
  }
  return true
}
defineExpose({ validate })
</script>

<template>
  <!-- Sits inside the page's shared content shell: no competing width/margin. -->
  <section class="min-w-0 w-full space-y-5">
    <CommonAppFormErrorSummary :form-errors="error ? [error] : []" />
    <p v-if="status" role="status" class="text-sm text-success">{{ status }}</p>
    <p v-if="config.botTokenConfigured" class="text-sm text-muted">{{ t('telegram.botTokenSaved') }}</p>
    <UAlert
      v-if="updatesInactive"
      color="warning"
      variant="subtle"
      icon="i-lucide-plug-zap-off"
      :description="t('telegram.updatesInactive')" />
    <p class="text-xs text-muted">{{ t('telegram.workerStatus') }}: {{ workerStatusText }}</p>
    <div class="grid gap-4 sm:grid-cols-2">
      <!-- Card A: Client Group — Service Order notifications to one group -->
      <fieldset class="space-y-3 rounded-lg border border-default p-4">
        <legend class="px-1 text-sm font-semibold">{{ t('telegram.clientGroup') }}</legend>
        <p class="text-sm text-muted">{{ t('telegram.clientPurpose') }}</p>
        <USwitch
          :model-value="config.clientEnabled ?? false"
          :disabled="!canManage || pending"
          :label="t('telegram.enableNotifications')"
          @update:model-value="value => patch({ clientEnabled: value })" />
        <UFormField :label="t('telegram.clientChatId')">
          <UInput
            :model-value="config.clientGroupId ?? ''"
            type="text"
            inputmode="numeric"
            placeholder="-1001234567890"
            :disabled="!canManage || pending"
            class="w-full font-mono"
            @update:model-value="value => patch({ clientGroupId: String(value ?? '') })" />
        </UFormField>
        <p class="text-sm">
          {{ t('telegram.connectionStatus') }}:
          <UBadge :color="config.clientConnectionStatus === 'connected' ? 'success' : 'neutral'" variant="subtle">
            {{ statusText(config.clientConnectionStatus) }}
          </UBadge>
        </p>
        <p v-if="config.clientLastTestMessage" class="text-xs text-muted">{{ config.clientLastTestMessage }}</p>
        <div class="space-y-1">
          <p class="text-sm font-medium">{{ t('telegram.serviceOrderEvents') }}</p>
          <UCheckbox
            v-for="key in CLIENT_EVENT_KEYS"
            :key="key"
            :model-value="config.clientEvents?.[key] ?? true"
            :label="t(CLIENT_EVENT_LABELS[key])"
            :disabled="!canManage || pending"
            @update:model-value="value => updateClientEvent(key, value === true)" />
        </div>
        <div v-if="canManage" class="flex flex-wrap gap-2">
          <UButton
            variant="outline"
            :loading="pending"
            :label="t('lcs.connection.test')"
            @click="perform({ clientEnabled: config.clientEnabled, clientGroupId: config.clientGroupId, clientEvents: config.clientEvents }, () => appConfig.testTelegramClientConnection())" />
          <UButton
            variant="outline"
            :loading="pending"
            :disabled="!config.clientGroupId"
            :label="t('telegram.sendTest')"
            @click="sendTest(() => appConfig.sendTestTelegramClientMessage())" />
        </div>
      </fieldset>

      <!-- Card B: Admin Bot — alerts to the verified administrator private chat -->
      <fieldset class="space-y-3 rounded-lg border border-default p-4">
        <legend class="px-1 text-sm font-semibold">{{ t('telegram.adminBot') }}</legend>
        <p class="text-sm text-muted">{{ t('telegram.adminPurpose') }}</p>
        <USwitch
          :model-value="config.enabled ?? false"
          :disabled="!canManage || pending"
          :label="t('telegram.enableAdminAlerts')"
          @update:model-value="value => patch({ enabled: value })" />
        <p class="text-sm">
          {{ t('telegram.verifiedRecipients') }}:
          <UBadge :color="recipientCount > 0 ? 'success' : 'neutral'" variant="subtle">
            {{ recipientCount }}
          </UBadge>
        </p>
        <p class="text-xs text-muted">{{ t('telegram.recipientsHelp') }}</p>
        <div class="space-y-1">
          <p class="text-sm font-medium">{{ t('telegram.alertEvents') }}</p>
          <UCheckbox
            v-for="key in ALERT_CATEGORY_KEYS"
            :key="key"
            :model-value="alertRules[key]?.enabled ?? false"
            :label="t(`telegram.${key}`)"
            :disabled="!canManage || pending"
            @update:model-value="value => updateRule(key, value === true)" />
        </div>
        <div v-if="canManage" class="flex flex-wrap gap-2">
          <UButton
            v-if="recipientCount > 0"
            variant="outline"
            :loading="pending"
            :disabled="!config.enabled"
            :label="t('telegram.sendTestAlert')"
            @click="sendTest(() => appConfig.sendTestTelegramMessage())" />
          <p v-else class="text-xs text-muted">{{ t('telegram.noRecipients') }}</p>
        </div>
      </fieldset>
    </div>
  </section>
</template>
