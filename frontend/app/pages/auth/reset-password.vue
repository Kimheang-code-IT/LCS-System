<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  clearPasswordResetSession,
  getPasswordResetSession,
} from '~/utils/auth/password-reset'
import { apiErrorDetails } from '~/utils/freight/errors'

definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const { resetPasswordWithCode } = useAuth()
const submitting = ref(false)
const formError = ref('')
const session = ref(getPasswordResetSession())
const resetForm = useTemplateRef<{
  formRef?: {
    setErrors: (errors: { name: string, message: string }[]) => void
    clear: () => void
  }
}>('resetForm')

/** Errors are placed on the field they belong to, or just above the submit button. */
function clearErrors() {
  formError.value = ''
  resetForm.value?.formRef?.clear()
}

function showErrors(error: unknown, fallback: string) {
  const { message, fieldErrors } = apiErrorDetails(error)
  const known = ['password', 'passwordConfirmation']
  const entries = Object.entries(fieldErrors || {})
    .filter(([name, text]) => known.includes(name) && text)
    .map(([name, text]) => ({ name, message: text }))
  formError.value = ''
  if (entries.length) {
    resetForm.value?.formRef?.setErrors(entries)
    return
  }
  formError.value = message || fallback
}

usePageSeo({
  title: () => t('pages.forgetPassword.resetTitle'),
  description: () => t('pages.forgetPassword.resetDesc'),
  robots: 'noindex, nofollow',
})

onMounted(() => {
  session.value = getPasswordResetSession()
  if (!session.value?.email) {
    void router.replace('/auth/forget-password')
    return
  }
  if (!session.value.verified || !session.value.code) {
    void router.replace('/auth/verify-code')
  }
})

const schema = computed(() => z.object({
  password: z.string().min(8, { error: t('pages.forgetPassword.passwordMin') }).max(20, { error: t('pages.forgetPassword.passwordMax') }),
  passwordConfirmation: z.string().min(8, { error: t('pages.forgetPassword.passwordMin') }).max(20, { error: t('pages.forgetPassword.passwordMax') }),
}).refine(data => data.password === data.passwordConfirmation, {
  message: t('pages.forgetPassword.passwordMismatch'),
  path: ['passwordConfirmation'],
}))

const fields = computed(() => [
  {
    name: 'password',
    type: 'password' as const,
    size: 'lg' as const,
    label: t('pages.forgetPassword.newPassword'),
    placeholder: t('pages.forgetPassword.newPasswordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
  {
    name: 'passwordConfirmation',
    type: 'password' as const,
    size: 'lg' as const,
    label: t('pages.forgetPassword.confirmPassword'),
    placeholder: t('pages.forgetPassword.confirmPasswordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
])

type Schema = {
  password: string
  passwordConfirmation: string
}

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value || !session.value?.email || !session.value.code) return
  clearErrors()
  submitting.value = true
  try {
    await resetPasswordWithCode({
      email: session.value.email,
      code: session.value.code,
      password: payload.data.password,
      passwordConfirmation: payload.data.passwordConfirmation,
    })
    clearPasswordResetSession()
    toast.add({
      title: t('pages.forgetPassword.resetSuccess'),
      description: t('pages.forgetPassword.resetSuccessDesc'),
      color: 'success',
    })
    await router.push('/auth/login')
  }
  catch (error) {
    showErrors(error, t('pages.forgetPassword.resetFailedDesc'))
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="resetForm"
      :schema="schema"
      :title="t('pages.forgetPassword.resetTitle')"
      icon="i-lucide-lock-keyhole"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.forgetPassword.resetSubmit'),
        class: 'w-full h-10! text-xl font-normal',
        loading: submitting,
      }"
      @submit="onSubmit"
    >
      <template #leading>
        <img src="/logo.png" alt="Logo" class="mx-auto h-20 w-auto">
      </template>

      <template #description>
        <p class="text-center text-sm text-muted">
          {{ t('pages.forgetPassword.resetDesc', { email: session?.email || '…' }) }}
        </p>
      </template>

      <template #footer>
        <div class="space-y-2 text-center">
          <p v-if="formError" class="flex items-start gap-2 text-left text-sm text-error" role="alert">
            <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" />
            <span>{{ formError }}</span>
          </p>
          <UButton
            variant="link"
            size="sm"
            to="/auth/login"
            class="text-muted-foreground underline"
          >
            <UIcon name="i-lucide-arrow-left" class="mr-1" />
            {{ t('pages.forgetPassword.backToLogin') }}
          </UButton>
          <div>
            <span class="text-sm font-normal text-muted">{{ $t('settings.aboutCopyright') }}</span>
          </div>
        </div>
      </template>
    </UAuthForm>
  </div>
</template>
