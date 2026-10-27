<script setup lang="ts">
import { useAuth } from '~/composables/auth/useAuth'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateRecoveryForm } from '~/utils/auth/recovery'

definePageMeta({ layout: 'auth' })
const { t } = useI18n()
const { requestPasswordReset } = useAuth()
const identifier = ref('')
const sent = ref(false)
const submitting = ref(false)
const validation = useFormValidation({ t: key => t(key), order: () => ['identifier'] })
async function submit() {
  if (submitting.value) return
  validation.reset()
  if (validation.applyFailures(validateRecoveryForm({ identifier: identifier.value }, () => t('telegram.identifier')))) return
  submitting.value = true
  try { await requestPasswordReset(identifier.value.trim()); sent.value = true }
  catch (error) { validation.applyServerError(error) }
  finally { submitting.value = false }
}
useHead({ title: () => t('pages.forgetPassword.title'), meta: [{ name: 'robots', content: 'noindex, nofollow' }, { name: 'referrer', content: 'no-referrer' }] })
</script>

<template>
  <section class="mx-auto w-full max-w-md space-y-6">
    <h1 class="text-center text-2xl font-semibold">{{ t('pages.forgetPassword.title') }}</h1>
    <p class="text-sm text-muted">{{ t('telegram.recoveryHint') }}</p>
    <UAlert v-if="sent" color="success" :description="t('telegram.genericRecovery')" />
    <CommonAppFormErrorSummary :form-errors="validation.formErrors.value" />
    <form class="space-y-4" @submit.prevent="submit">
      <UFormField :label="t('telegram.identifier')" :error="validation.fieldErrors.value.identifier" required>
        <UInput
v-model="identifier"
data-field-key="identifier"
autocomplete="username"
class="w-full"
:maxlength="255"
@update:model-value="validation.clearFieldError('identifier')" />
      </UFormField>
      <UButton
type="submit"
:loading="submitting"
:label="t('pages.forgetPassword.submitBtn')"
block />
    </form>
    <UButton to="/auth/login" variant="link" :label="t('pages.forgetPassword.backToLogin')" />
  </section>
</template>
