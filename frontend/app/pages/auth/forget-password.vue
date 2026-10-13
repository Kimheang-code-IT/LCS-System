<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'
import { startPasswordReset } from '~/utils/auth/password-reset'
import { apiErrorDetails } from '~/utils/freight/errors'

definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const { requestPasswordReset } = useAuth()
const submitting = ref(false)
const formError = ref('')
const forgetForm = useTemplateRef<{
  formRef?: {
    setErrors: (errors: { name: string, message: string }[]) => void
    clear: () => void
  }
}>('forgetForm')

/** Errors are placed on the field they belong to, or just above the submit button. */
function clearErrors() {
  formError.value = ''
  forgetForm.value?.formRef?.clear()
}

function showErrors(error: unknown, fallback: string) {
  const { message, fieldErrors } = apiErrorDetails(error)
  const entries = Object.entries(fieldErrors || {})
    .filter(([name, text]) => name === 'email' && text)
    .map(([name, text]) => ({ name, message: text }))
  formError.value = ''
  if (entries.length) {
    forgetForm.value?.formRef?.setErrors(entries)
    return
  }
  formError.value = message || fallback
}

usePageSeo({
  title: () => t('pages.forgetPassword.title'),
  description: () => t('pages.forgetPassword.desc'),
  robots: 'noindex, nofollow',
})

const schema = computed(() => z.object({
  email: z.email({ error: t('pages.auth.emailRequired') }),
}))

const fields = computed(() => [
  {
    name: 'email',
    type: 'email' as const,
    size: 'lg' as const,
    label: t('pages.auth.email'),
    placeholder: t('pages.auth.emailPlaceholder'),
    required: true,
    autocomplete: 'email',
  },
])

type Schema = { email: string }

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value) return
  clearErrors()
  submitting.value = true
  try {
    const email = payload.data.email.trim()
    await requestPasswordReset(email)
    startPasswordReset(email)
    toast.add({
      title: t('pages.forgetPassword.sentTitle'),
      description: t('pages.forgetPassword.sentDesc', { email }),
      color: 'success',
    })
    await router.push('/auth/verify-code')
  }
  catch (error) {
    showErrors(error, t('api.somethingWentWrong'))
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="forgetForm"
      :schema="schema"
      :title="t('pages.forgetPassword.title')"
      icon="i-lucide-key-round"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.forgetPassword.submitBtn'),
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
          {{ t('pages.forgetPassword.desc') }}
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
