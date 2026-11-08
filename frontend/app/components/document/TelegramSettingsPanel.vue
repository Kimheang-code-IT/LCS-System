<script setup lang="ts">
import { useSettingsRepositories, useTelegramRepository } from '~/repositories'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { TelegramConfig } from '~/types/settings'

/**
 * Settings → Telegram Configuration. Exactly two configuration blocks:
 * Client Group (Service Order notifications) and Admin Group (system alerts).
 * The shared bot credential stays in the tab's form fields above (masked).
 */
const props = defineProps<{ config: TelegramConfig, canManage: boolean }>()
const emit = defineEmits<{ refresh: [], 'update:rules': [value: TelegramConfig['rules']] }>()
const { t } = useI18n()
const toast = useToast()
const repo = useTelegramRepository()
const { appConfig } = useSettingsRepositories()

const pending = ref(false)
const error = ref('')
const status = ref('')
const pairing = ref<TelegramPairing | null>(null)
const candidate = ref<{ name: string | null, verified: boolean } | null>(null)

// --- Client Group draft -------------------------------------------------------
const clientEnabled = ref(props.config.clientEnabled ?? false)
const clientGroupId = ref(props.config.clientGroupId ?? '')
const clientBotToken = ref('')
const clientEvents = ref<Record<string, boolean>>({ ...(props.config.clientEvents ?? {}) })

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

function statusText(value: string | undefined): string {
  if (!value || value === 'not_tested') return t('telegram.notTested')
  if (value === 'connected') return t('telegram.connected')
  return t('telegram.sendFailed')
}

async function perform(action: () => Promise<unknown>, success?: () => void) {
  if (pending.value) return
  pending.value = true
  error.value = ''
  try {
    await action()
    success?.()
  }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')) }
  finally { pending.value = false }
}

async function saveClientGroup(updated?: boolean) {
  // Send the full section like the page Save does: the backend preserves blank
  // secrets, so an untouched token field can never wipe a stored credential.
  const patch: TelegramConfig = {
    ...props.config,
    clientEnabled: clientEnabled.value,
    clientGroupId: clientGroupId.value.trim(),
    clientEvents: { ...(props.config.clientEvents ?? {}), ...clientEvents.value },
    ...(clientBotToken.value.trim() ? { clientBotToken: clientBotToken.value.trim() } : {}),
  }
  await appConfig.update({ telegram: patch })
  clientBotToken.value = ''
  if (updated) status.value = t('telegram.clientSaved')
  emit('refresh')
}

async function pair() { pairing.value = await repo.pairGroup(); candidate.value = null }
async function check() { candidate.value = await repo.candidate() }
async function confirm() {
  if (!pairing.value) return
  await repo.confirmGroup(pairing.value.challenge)
  pairing.value = null
  candidate.value = null
  emit('refresh')
}
async function disableIntegration(removeBotToken = false) {
  await appConfig.update({ telegram: { ...props.config, enabled: false, botToken: '', ...(removeBotToken ? { removeBotToken: true } : {}) } })
  emit('refresh')
}
/** Admin alert categories toggle in place; never invent rules when none stored. */
const alertRules = computed(() => props.config.rules ?? {})
function toggleRule(key: string, value: boolean | 'indeterminate') {
  const rule = alertRules.value[key]
  if (!rule) return
  emit('update:rules', { ...alertRules.value, [key]: { ...rule, enabled: value === true } })
}
</script>

<template>
  <section class="mx-auto w-full max-w-5xl space-y-5 px-6 py-6">
    <CommonAppFormErrorSummary :form-errors="error ? [error] : []" />
    <p v-if="status" role="status" class="text-sm text-success">{{ status }}</p>
    <div class="grid gap-5 sm:grid-cols-2">
      <!-- Block A: Client Group — Service Order notifications -->
      <fieldset class="space-y-3 rounded-lg border border-default p-4">
        <legend class="px-1 text-sm font-semibold">{{ t('telegram.clientGroup') }}</legend>
        <p class="text-sm text-muted">{{ t('telegram.clientPurpose') }}</p>
        <USwitch
          v-model="clientEnabled"
          :disabled="!canManage || pending"
          :label="t('telegram.enableNotifications')" />
        <UFormField :label="t('telegram.clientChatId')">
          <UInput
            v-model="clientGroupId"
            type="text"
            inputmode="numeric"
            placeholder="-1001234567890"
            :disabled="!canManage || pending"
            class="w-full font-mono" />
        </UFormField>
        <UFormField
          :label="t('telegram.clientBotToken')"
          :help="config.clientBotTokenConfigured ? t('telegram.tokenConfigured') : t('telegram.sharedBotToken')">
          <UInput
            v-model="clientBotToken"
            type="password"
            :disabled="!canManage || pending"
            class="w-full" />
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
            v-model="clientEvents[key]"
            :label="t(CLIENT_EVENT_LABELS[key])"
            :disabled="!canManage || pending" />
        </div>
        <div v-if="canManage" class="flex flex-wrap gap-2">
          <UButton
            variant="outline"
            :loading="pending"
            :label="t('lcs.connection.test')"
            @click="perform(async () => { status = (await appConfig.testTelegramClientConnection()).message; emit('refresh') })" />
          <UButton
            variant="outline"
            :loading="pending"
            :disabled="!config.clientGroupId"
            :label="t('telegram.sendTest')"
            @click="perform(async () => { status = (await appConfig.sendTestTelegramClientMessage()).message })" />
          <UButton
            :loading="pending"
            :label="t('telegram.saveConfig')"
            @click="perform(() => saveClientGroup(true), () => toast.add({ title: t('telegram.saved'), color: 'success' }))" />
        </div>
      </fieldset>

      <!-- Block B: Admin Group — system health and operational alerts -->
      <fieldset class="space-y-3 rounded-lg border border-default p-4">
        <legend class="px-1 text-sm font-semibold">{{ t('telegram.adminGroupTitle') }}</legend>
        <p class="text-sm text-muted">{{ t('telegram.adminPurpose') }}</p>
        <p class="text-sm">
          {{ t('telegram.connectionStatus') }}:
          <UBadge :color="config.adminGroupName ? 'success' : 'neutral'" variant="subtle">
            {{ config.adminGroupName || t('telegram.notConnected') }}
          </UBadge>
        </p>
        <p v-if="config.adminGroupVerifiedAt" class="text-xs text-muted">{{ config.adminGroupVerifiedAt }}</p>
        <div class="space-y-1">
          <p class="text-sm font-medium">{{ t('telegram.alertRules') }}</p>
          <UCheckbox
            v-for="(rule, key) in alertRules"
            :key="key"
            :model-value="rule.enabled"
            :label="t(`telegram.${key}`)"
            :disabled="!canManage || pending"
            @update:model-value="toggleRule(key, $event)" />
        </div>
        <p class="text-sm text-muted">{{ config.lastTestMessage || statusText(config.connectionStatus) }}</p>
        <div v-if="canManage" class="flex flex-wrap gap-2">
          <UButton
            v-if="config.enabled"
            :loading="pending"
            :label="t('telegram.registerWebhook')"
            @click="perform(async () => { status = (await repo.registerWebhook()).status })" />
          <UButton :loading="pending" :label="t('telegram.pairGroup')" @click="perform(pair)" />
          <UButton
            v-if="config.adminGroupVerifiedAt"
            variant="outline"
            :disabled="pending"
            :label="t('lcs.connection.test')"
            @click="perform(async () => { status = (await appConfig.sendTestTelegramMessage()).message })" />
          <UButton
            v-if="config.adminGroupVerifiedAt"
            color="neutral"
            variant="outline"
            :disabled="pending"
            :label="t('telegram.disconnect')"
            @click="perform(async () => { await repo.disconnectGroup(); emit('refresh') })" />
        </div>
      </fieldset>
    </div>
    <div v-if="pairing" class="space-y-3 rounded-md border border-default p-4">
      <p class="text-sm">{{ t('telegram.groupInstructions') }}</p>
      <code class="block break-all rounded bg-muted p-3">{{ pairing.command }}</code>
      <p class="text-sm text-muted">{{ t('telegram.expires') }}: {{ pairing.expiresAt }}</p>
      <UButton :disabled="pending" :label="t('telegram.checkCandidate')" @click="perform(check)" />
      <p v-if="candidate">{{ candidate.name || t('telegram.waiting') }}</p>
      <UButton
        v-if="candidate?.verified"
        :disabled="pending"
        :label="t('telegram.confirmGroup')"
        @click="perform(confirm)" />
    </div>
    <p class="text-sm text-muted">{{ t('telegram.privateOnly') }}</p>
    <div v-if="canManage" class="flex flex-wrap gap-2 border-t border-default pt-4">
      <UButton
        color="neutral"
        variant="outline"
        :disabled="pending"
        :label="t('telegram.disable')"
        @click="perform(() => disableIntegration())" />
      <UButton
        color="error"
        variant="outline"
        :disabled="pending"
        :label="t('telegram.removeToken')"
        @click="perform(() => disableIntegration(true))" />
    </div>
  </section>
</template>
