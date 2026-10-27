<script setup lang="ts">
import { useTelegramRepository } from '~/repositories'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateFieldValue } from '~/utils/validation/field-rules'
import type { TelegramPairing } from '~/types/settings'

const { t } = useI18n()
const repo = useTelegramRepository()
const link = ref<Awaited<ReturnType<typeof repo.myLink>> | null>(null)
const pairing = ref<TelegramPairing | null>(null)
const currentPassword = ref('')
const pending = ref(false)
const validation = useFormValidation({ t: key => t(key), order: () => ['currentPassword'] })
async function refresh() {
  try { link.value = await repo.myLink() }
  catch (error) { validation.applyServerError(error) }
}
async function change() {
  validation.reset()
  const issues = validateFieldValue(currentPassword.value, { required: true, maxLength: 128 })
  if (issues) { validation.setFieldError('currentPassword', t('lcs.userProfile.currentPasswordRequired')); return }
  if (pending.value) return
  pending.value = true
  try {
    if (link.value?.connected) {
      await repo.disconnectPrivate(currentPassword.value)
      pairing.value = null
    }
    else { pairing.value = await repo.pairPrivate(currentPassword.value) }
    currentPassword.value = ''
    await refresh()
  }
  catch (error) { validation.applyServerError(error) }
  finally { pending.value = false }
}
onMounted(refresh)
onBeforeUnmount(() => { currentPassword.value = ''; pairing.value = null })
</script>

<template>
  <section class="space-y-3 border-t border-default pt-4">
    <h4 class="text-sm font-semibold">{{ t('telegram.privateAccount') }}</h4>
    <p>{{ link?.connected ? t('telegram.connected') : t('telegram.notConnected') }}</p>
    <p v-if="link?.connected" class="text-sm text-muted">{{ link.displayName }} · {{ link.verifiedAt }}</p>
    <CommonAppFormErrorSummary :form-errors="validation.formErrors.value" />
    <form class="space-y-3" @submit.prevent="change">
      <UFormField :label="t('lcs.userProfile.currentPassword')" :error="validation.fieldErrors.value.currentPassword" required>
        <UInput
v-model="currentPassword"
type="password"
autocomplete="current-password"
data-field-key="currentPassword"
class="w-full"
@update:model-value="validation.clearFieldError('currentPassword')" />
      </UFormField>
      <UButton type="submit" :loading="pending" :label="t(link?.connected ? 'telegram.disconnect' : 'telegram.connect')" />
    </form>
    <div v-if="pairing && !link?.connected" class="space-y-2">
      <p class="text-sm text-muted">{{ t('telegram.privateInstructions') }}</p>
      <UButton
:to="pairing.url"
target="_blank"
rel="noopener noreferrer"
:label="t('telegram.openBot')" />
      <p class="text-sm">{{ t('telegram.expires') }}: {{ pairing.expiresAt }}</p>
      <UButton color="neutral" :label="t('telegram.checkConnection')" @click="refresh" />
    </div>
  </section>
</template>
