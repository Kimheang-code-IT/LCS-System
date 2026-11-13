<script setup lang="ts">
import { useTelegramRepository } from '~/repositories'
import { useAuthStore } from '~/stores/auth'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateFieldValue } from '~/utils/validation/field-rules'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { formatDateTime } from '~/utils/format/format-service'

/**
 * Profile → Telegram connection with a 6-digit verification code:
 * generate here, send `/verify CODE` to the bot, then this section refreshes
 * automatically and shows the verified Telegram identity. Only users holding
 * ``telegram.chatbot.use`` ever see the section; the API enforces the same rule.
 */
const { t } = useI18n()
const auth = useAuthStore()
const repo = useTelegramRepository()
const allowed = computed(() => auth.canAccessPage('telegram.chatbot.use'))
const link = ref<Awaited<ReturnType<typeof repo.myLink>> | null>(null)
const code = ref<{ code: string, expiresAt: string, botUsername: string } | null>(null)
const generating = ref(false)
const copied = ref(false)
const now = ref(Date.now())
let clock: ReturnType<typeof setInterval> | undefined
let refreshTimer: ReturnType<typeof setInterval> | undefined

const validation = useFormValidation({ t: key => t(key), order: () => ['currentPassword'] })
const disconnectOpen = ref(false)
const currentPassword = ref('')
const disconnecting = ref(false)
const actionError = ref('')

const remainingSeconds = computed(() => {
  if (!code.value) return 0
  const expires = Date.parse(code.value.expiresAt)
  if (!Number.isFinite(expires)) return 0
  return Math.max(0, Math.ceil((expires - now.value) / 1000))
})
const codeExpired = computed(() => Boolean(code.value) && remainingSeconds.value <= 0)
const countdown = computed(() => {
  const seconds = remainingSeconds.value
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
})
const verifyCommand = computed(() => (code.value ? `/verify ${code.value.code}` : ''))
const botUsername = computed(() => link.value?.botUsername || code.value?.botUsername || '')

type State = 'disconnected' | 'waiting' | 'connected' | 'expired'
const connectionState = computed<State>(() => {
  if (link.value?.connected) return 'connected'
  if (code.value) return codeExpired.value ? 'expired' : 'waiting'
  return 'disconnected'
})
const statusLabel = computed(() => t(`telegram.connectionStates.${connectionState.value}`))
const statusColor = computed(() => (connectionState.value === 'connected' ? 'success' : connectionState.value === 'expired' ? 'warning' : 'neutral'))

async function refresh() {
  if (!allowed.value) return
  try { link.value = await repo.myLink() }
  catch { link.value = null }
}

const clientBusy = computed(() => generating.value || disconnecting.value)

async function generate() {
  if (generating.value || clientBusy.value) return
  actionError.value = ''
  generating.value = true
  try {
    code.value = await repo.verificationCode()
    now.value = Date.now()
    copied.value = false
    await refresh()
  }
  catch (error) { actionError.value = apiErrorMessage(error, t('telegram.failed')) }
  finally { generating.value = false }
}

async function copyCommand() {
  if (!verifyCommand.value) return
  try {
    await navigator.clipboard.writeText(verifyCommand.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
  catch { actionError.value = t('telegram.copyFailed') }
}

function openDisconnect() {
  validation.reset()
  actionError.value = ''
  currentPassword.value = ''
  disconnectOpen.value = true
}

async function confirmDisconnect() {
  validation.reset()
  const issues = validateFieldValue(currentPassword.value, { required: true, maxLength: 128 })
  if (issues) { validation.setFieldError('currentPassword', t('lcs.userProfile.currentPasswordRequired')); return }
  if (disconnecting.value) return
  disconnecting.value = true
  actionError.value = ''
  try {
    await repo.disconnectPrivate(currentPassword.value)
    code.value = null
    disconnectOpen.value = false
    currentPassword.value = ''
    await refresh()
  }
  catch (error) { actionError.value = apiErrorMessage(error, t('telegram.failed')) }
  finally { disconnecting.value = false }
}

// One-second clock for the countdown; a slow refresh picks up verification
// completed in Telegram without introducing a websocket.
watch(allowed, value => { if (value) void refresh() }, { immediate: true })
onMounted(() => {
  clock = setInterval(() => { now.value = Date.now() }, 1000)
  refreshTimer = setInterval(() => {
    if (connectionState.value === 'waiting') void refresh()
  }, 5000)
})
onBeforeUnmount(() => {
  if (clock) clearInterval(clock)
  if (refreshTimer) clearInterval(refreshTimer)
  currentPassword.value = ''
  code.value = null
})
</script>

<template>
  <section v-if="allowed" class="space-y-3 border-t border-default pt-4">
    <h4 class="text-sm font-semibold">{{ t('telegram.connectionTitle') }}</h4>
    <div class="space-y-1 text-sm">
      <p>{{ t('telegram.botConnection') }}:
        <span v-if="botUsername" class="font-mono">@{{ botUsername.replace(/^@/, '') }}</span>
        <span v-else class="text-muted">{{ t('telegram.notConnected') }}</span>
      </p>
      <p>{{ t('telegram.connectionStatus') }}:
        <UBadge :color="statusColor" variant="subtle">{{ statusLabel }}</UBadge>
      </p>
    </div>

    <CommonAppFormErrorSummary :form-errors="actionError ? [actionError] : []" />

    <!-- Before verification: one code, one copy action, one countdown. -->
    <div v-if="!link?.connected" class="space-y-3">
      <UButton :loading="generating" :label="code ? t('telegram.regenerateCode') : t('telegram.generateCode')" @click="generate" />
      <div v-if="code && !codeExpired" class="space-y-2 rounded-md border border-default p-3">
        <p class="text-xs text-muted">{{ t('telegram.sendCommandHint', { bot: '@' + botUsername.replace(/^@/, '') }) }}</p>
        <p class="font-mono text-2xl tracking-[0.3em]">{{ code.code }}</p>
        <p class="text-sm">{{ t('telegram.codeExpiresIn') }}: <span class="font-mono">{{ countdown }}</span></p>
        <!-- User-facing hint stays short: the environment details live in the
             admin Telegram settings tab, the only diagnostic screen. -->
        <UAlert
          v-if="link && link.updatesActive === false"
          color="warning"
          variant="subtle"
          icon="i-lucide-plug-zap-off"
          :description="t('telegram.updatesWaitingHint')" />
        <div class="flex flex-wrap gap-2">
          <UButton
color="neutral"
variant="outline"
:label="copied ? t('telegram.copied') : t('telegram.copyCommand')"
@click="copyCommand" />
        </div>
      </div>
      <p v-else-if="codeExpired" class="text-sm text-warning">{{ t('telegram.codeExpired') }}</p>
    </div>

    <!-- After verification: the Telegram identity linked to this LCS account. -->
    <div v-else class="space-y-1 text-sm">
      <p>{{ t('telegram.username') }}: <span class="font-mono">{{ link.username || link.displayName }}</span></p>
      <p>{{ t('telegram.telegramUserId') }}: <span class="font-mono">{{ link.telegramUserId }}</span></p>
      <p v-if="link.verifiedAt">{{ t('telegram.verifiedDate') }}: {{ formatDateTime(link.verifiedAt) }}</p>
      <UButton
color="error"
variant="outline"
:label="t('telegram.disconnect')"
@click="openDisconnect" />
    </div>

    <UModal v-model:open="disconnectOpen" :title="t('telegram.disconnectConfirmTitle')" :dismissible="!disconnecting">
      <template #body>
        <div class="space-y-3">
          <p class="text-sm text-muted">{{ t('telegram.disconnectConfirmHelp') }}</p>
          <UFormField :label="t('lcs.userProfile.currentPassword')" :error="validation.fieldErrors.value.currentPassword" required>
            <UInput
              v-model="currentPassword"
              type="password"
              autocomplete="current-password"
              data-field-key="currentPassword"
              class="w-full"
              @update:model-value="validation.clearFieldError('currentPassword')" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
color="neutral"
variant="ghost"
:label="t('lcs.common.cancel')"
:disabled="disconnecting"
@click="disconnectOpen = false" />
          <UButton
color="error"
:loading="disconnecting"
:label="t('telegram.disconnect')"
@click="confirmDisconnect" />
        </div>
      </template>
    </UModal>
  </section>
</template>
