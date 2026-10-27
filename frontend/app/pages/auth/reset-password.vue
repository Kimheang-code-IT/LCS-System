<script setup lang="ts">
import { useAuth } from '~/composables/auth/useAuth'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { takeRecoveryToken, validateRecoveryForm } from '~/utils/auth/recovery'
import { validatePasswordStrength } from '~/utils/validation/field-rules'

definePageMeta({ layout: 'auth' })
const { t } = useI18n()
const router = useRouter()
const { verifyPasswordResetToken, resetPasswordWithToken } = useAuth()
const token = ref('')
const verified = ref(false)
const checking = ref(true)
const submitting = ref(false)
const password = ref('')
const passwordConfirmation = ref('')
const validation = useFormValidation({ t: key => t(key), order: () => ['password', 'passwordConfirmation'] })
const label = (key: string) => t(key === 'passwordMismatch' ? 'validation.passwordMismatch' : key === 'password' ? 'pages.forgetPassword.newPassword' : 'pages.forgetPassword.confirmPassword')
/** Enter, or the submit button, is refused until every rule and the match pass. */
const passwordsValid = computed(() => !validatePasswordStrength(password.value) && password.value === passwordConfirmation.value)
useHead({ title: () => t('pages.forgetPassword.resetTitle'), meta: [{ name: 'robots', content: 'noindex, nofollow' }, { name: 'referrer', content: 'no-referrer' }] })
onMounted(async () => {
  token.value = takeRecoveryToken(window.location, window.history)
  try {
    if (!token.value) throw new Error('invalid_recovery_link')
    await verifyPasswordResetToken(token.value)
    verified.value = true
  }
  catch { validation.addFormError(t('telegram.invalidRecovery')) }
  finally { checking.value = false }
})
onBeforeUnmount(() => { token.value = ''; password.value = ''; passwordConfirmation.value = '' })
async function submit() {
  if (!verified.value || submitting.value || !passwordsValid.value) return
  validation.reset()
  if (validation.applyFailures(validateRecoveryForm({ password: password.value, passwordConfirmation: passwordConfirmation.value }, label))) return
  submitting.value = true
  try {
    await resetPasswordWithToken(token.value, password.value, passwordConfirmation.value)
    useAuthStore().clearSession()
    token.value = ''
    password.value = ''
    passwordConfirmation.value = ''
    await router.replace('/auth/login')
  }
  catch (error) { validation.applyServerError(error) }
  finally { submitting.value = false }
}
</script>

<template>
  <section class="mx-auto w-full max-w-md space-y-6">
    <h1 class="text-center text-2xl font-semibold">{{ t('pages.forgetPassword.resetTitle') }}</h1>
    <p v-if="checking" class="text-sm text-muted">{{ t('telegram.checkingLink') }}</p>
    <CommonAppFormErrorSummary :form-errors="validation.formErrors.value" />
    <form v-if="verified" class="space-y-4" @submit.prevent="submit">
      <UFormField :label="label('password')" :error="validation.fieldErrors.value.password" required>
        <UInput
v-model="password"
type="password"
autocomplete="new-password"
data-field-key="password"
class="w-full"
@update:model-value="validation.clearFieldError('password')" />
        <CommonAppPasswordRequirements :value="password" />
      </UFormField>
      <UFormField :label="label('passwordConfirmation')" :error="validation.fieldErrors.value.passwordConfirmation" required>
        <UInput
v-model="passwordConfirmation"
type="password"
autocomplete="new-password"
data-field-key="passwordConfirmation"
class="w-full"
@update:model-value="validation.clearFieldError('passwordConfirmation')" />
      </UFormField>
      <UButton
type="submit"
:loading="submitting"
:disabled="!passwordsValid || submitting"
:label="t('pages.forgetPassword.resetSubmit')"
block />
    </form>
    <UButton to="/auth/forget-password" variant="link" :label="t('pages.forgetPassword.title')" />
    <UButton to="/auth/login" variant="link" :label="t('pages.forgetPassword.backToLogin')" />
  </section>
</template>
