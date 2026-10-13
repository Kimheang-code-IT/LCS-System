<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'
import { useSetup } from '~/composables/auth/useSetup'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'
import { apiErrorDetails } from '~/utils/freight/errors'

definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const auth = useAuthStore()
const setup = useSetup()
const { loginWithCredentials } = useAuth()
const submitting = ref(false)
const formError = ref('')
const setupForm = useTemplateRef<{
  formRef?: {
    setErrors: (errors: { name: string, message: string }[]) => void
    clear: () => void
  }
}>('setupForm')

/** Errors are placed on the field they belong to, or just above the submit button. */
function clearErrors() {
  formError.value = ''
  setupForm.value?.formRef?.clear()
}

function showErrors(error: unknown, fallback: string) {
  const { message, fieldErrors } = apiErrorDetails(error)
  const known = ['name', 'email', 'password', 'passwordConfirmation']
  const entries = Object.entries(fieldErrors || {})
    .filter(([name, text]) => known.includes(name) && text)
    .map(([name, text]) => ({ name, message: text }))
  formError.value = ''
  if (entries.length) {
    setupForm.value?.formRef?.setErrors(entries)
    return
  }
  formError.value = message || fallback
}

usePageSeo({
  title: () => t('pages.setup.title'),
  description: () => t('pages.setup.description'),
  robots: 'noindex, nofollow',
})

const schema = computed(() => z.object({
  name: z.string().min(1, { error: t('pages.setup.nameRequired') }),
  email: z.email({ error: t('pages.auth.emailRequired') }),
  password: z.string().min(8, { error: t('pages.setup.passwordMin') }).max(20, { error: t('pages.setup.passwordMax') }),
  passwordConfirmation: z.string().min(8, { error: t('pages.setup.passwordMin') }).max(20, { error: t('pages.setup.passwordMax') }),
}))

const fields = computed<AuthFormField[]>(() => [
  {
    name: 'name',
    type: 'text',
    size: 'lg',
    label: t('pages.setup.adminName'),
    placeholder: t('pages.setup.adminNamePlaceholder'),
    required: false,
    autocomplete: 'name',
  },
  {
    name: 'email',
    type: 'email',
    size: 'lg',
    label: t('pages.setup.email'),
    placeholder: t('pages.auth.emailPlaceholder'),
    required: true,
    autocomplete: 'username',
  },
  {
    name: 'password',
    type: 'password',
    size: 'lg',
    label: t('pages.setup.password'),
    placeholder: t('pages.auth.passwordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
  {
    name: 'passwordConfirmation',
    type: 'password',
    size: 'lg',
    label: t('pages.setup.confirmPassword'),
    placeholder: t('pages.auth.passwordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
])

type Schema = {
  name: string
  email: string
  password: string
  passwordConfirmation: string
}

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value) return
  const data = payload.data

  clearErrors()
  if (data.password !== data.passwordConfirmation) {
    setupForm.value?.formRef?.setErrors([
      { name: 'passwordConfirmation', message: t('pages.setup.passwordMismatch') },
    ])
    return
  }

  submitting.value = true
  try {
    await setup.initialize({
      email: data.email.trim(),
      password: data.password,
      name: data.name.trim(),
    })

    try {
      const result = await loginWithCredentials(data.email.trim(), data.password)
      const user = result.data?.user
      if (user) {
        auth.login(user)
        await navigateTo('/', { replace: true })
        return
      }
    }
    catch {
      // Fall through to manual sign-in when auto-login fails.
    }

    await navigateTo('/auth/login', { replace: true })
  }
  catch (error) {
    showErrors(error, t('pages.setup.failed'))
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="setupForm"
      :schema="schema"
      :title="t('pages.setup.title')"
      icon="i-lucide-shield-check"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.setup.submit'),
        class: 'w-full h-10! text-lg font-normal',
        loading: submitting,
      }"
      @submit="onSubmit"
    >
      <template #leading>
        <img src="/logo.png" alt="Logo" class="mx-auto h-16 w-auto">
      </template>

      <template #footer>
        <p v-if="formError" class="flex items-start gap-2 text-sm text-error" role="alert">
          <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" />
          <span>{{ formError }}</span>
        </p>
      </template>
    </UAuthForm>
  </div>
</template>
