<script setup lang="ts">
import { useSettingsRepositories, useTelegramRepository } from '~/repositories'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { TelegramAlertRule, TelegramConfig, TelegramPairing } from '~/types/settings'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateFieldValue, type ValidationFailure } from '~/utils/validation/field-rules'

const props = defineProps<{ config: TelegramConfig, canManage: boolean }>()
const emit = defineEmits<{ refresh: [] }>()
const { t } = useI18n()
const repo = useTelegramRepository()
const { appConfig } = useSettingsRepositories()
async function disableIntegration(removeBotToken = false) {
  await appConfig.update({ telegram: { ...props.config, enabled: false, botToken: '', ...(removeBotToken ? { removeBotToken: true } : {}) } })
  emit('refresh')
}
const categories = ['security', 'backup', 'system', 'recovery'] as const
const rules = ref<Record<string, TelegramAlertRule>>({})
const validation = useFormValidation({ t: key => t(key), order: () => categories.flatMap(category => ['cooldownMinutes', 'maxAttempts'].map(key => `${category}.${key}`)) })
watch(() => props.config.rules, (value) => {
  rules.value = Object.fromEntries(categories.map(category => [category, { enabled: false, destination: category === 'recovery' ? 'PRIVATE' : 'ADMIN', minimumSeverity: category === 'recovery' ? 'INFO' : 'WARNING', cooldownMinutes: 15, notifyOnRecovery: true, maxAttempts: 3, ...value?.[category] }]))
}, { immediate: true })
const pending = ref(false)
const error = ref('')
const status = ref('')
const pairing = ref<TelegramPairing | null>(null)
const candidate = ref<{ name: string | null, verified: boolean } | null>(null)

async function perform(action: () => Promise<unknown>) {
  if (pending.value) return
  pending.value = true
  error.value = ''
  try { await action() }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')) }
  finally { pending.value = false }
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
async function saveRules() {
  validation.reset()
  const failures: ValidationFailure[] = []
  for (const category of categories) {
    const rule = rules.value[category]!
    for (const [key, max] of [['cooldownMinutes', 1440], ['maxAttempts', 5]] as const) {
      const issue = validateFieldValue(rule[key], { required: true, number: true, integer: true, min: 1, max })
      if (issue) failures.push({ key: `${category}.${key}`, label: t(`telegram.${key}`), ...issue })
    }
  }
  if (validation.applyFailures(failures)) return
  await perform(async () => { await appConfig.update({ telegram: { ...props.config, botToken: '', rules: rules.value } }); emit('refresh') })
}
</script>

<template>
  <div class="mx-auto w-full max-w-5xl space-y-6 px-6 py-6">
    <UAlert v-if="error" color="error" :description="error" />
    <UAlert v-if="status" color="success" :description="status" />
    <div v-if="canManage" class="flex flex-wrap gap-2">
      <UButton
color="neutral"
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
    <UCard>
      <template #header><h2 class="font-semibold">{{ t('telegram.webhook') }}</h2></template>
      <p class="mb-3 text-sm text-muted">{{ config.webhookStatus || t('telegram.notConnected') }}</p>
      <UButton
v-if="canManage"
:loading="pending"
:label="t('telegram.registerWebhook')"
@click="perform(async () => { status = (await repo.registerWebhook()).status })" />
    </UCard>
    <UCard>
      <template #header><h2 class="font-semibold">{{ t('telegram.adminGroup') }}</h2></template>
      <p>{{ config.adminGroupName || t('telegram.notConnected') }}</p>
      <p v-if="config.adminGroupVerifiedAt" class="text-sm text-muted">{{ config.adminGroupVerifiedAt }}</p>
      <div v-if="canManage" class="mt-4 flex flex-wrap gap-2">
        <UButton :loading="pending" :label="t('telegram.pairGroup')" @click="perform(pair)" />
        <UButton
v-if="config.adminGroupVerifiedAt"
:disabled="pending"
:label="t('lcs.connection.test')"
@click="perform(async () => { status = (await appConfig.sendTestTelegramMessage()).message })" />
        <UButton
v-if="config.adminGroupVerifiedAt"
color="neutral"
:disabled="pending"
:label="t('telegram.disconnect')"
@click="perform(async () => { await repo.disconnectGroup(); emit('refresh') })" />
      </div>
      <div v-if="pairing" class="mt-4 space-y-3">
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
    </UCard>
    <UCard>
      <template #header><h2 class="font-semibold">{{ t('telegram.passwordRecovery') }}</h2></template>
      <p class="text-sm text-muted">{{ t('telegram.privateOnly') }}</p>
    </UCard>
    <UCard>
      <template #header><h2 class="font-semibold">{{ t('telegram.alertRules') }}</h2></template>
      <CommonAppFormErrorSummary :form-errors="validation.formErrors.value" />
      <div v-for="category in categories" :key="category" class="mb-5 space-y-3 border-b border-default pb-4">
        <h3 class="font-medium">{{ t(`telegram.${category}`) }} · {{ rules[category]?.destination }}</h3>
        <template v-if="rules[category]">
          <USwitch v-model="rules[category]!.enabled" :disabled="!canManage" :label="t('telegram.enabled')" />
          <div class="grid gap-3 sm:grid-cols-2">
            <UFormField :label="t('telegram.minimumSeverity')">
              <USelect
v-model="rules[category]!.minimumSeverity"
:disabled="!canManage"
:items="['INFO', 'WARNING', 'CRITICAL']"
class="w-full" />
            </UFormField>
            <UFormField
v-for="field in ['cooldownMinutes', 'maxAttempts'] as const"
:key="field"
:label="t(`telegram.${field}`)"
:error="validation.fieldErrors.value[`${category}.${field}`]">
              <UInput
v-model.number="rules[category]![field]"
type="number"
:disabled="!canManage"
:data-field-key="`${category}.${field}`"
class="w-full" />
            </UFormField>
          </div>
          <USwitch v-model="rules[category]!.notifyOnRecovery" :disabled="!canManage" :label="t('telegram.notifyOnRecovery')" />
        </template>
      </div>
      <UButton
v-if="canManage"
:loading="pending"
:label="t('lcs.common.save')"
@click="saveRules" />
    </UCard>
    <DocumentTelegramDeliveryHistory :can-manage="canManage" />
  </div>
</template>
