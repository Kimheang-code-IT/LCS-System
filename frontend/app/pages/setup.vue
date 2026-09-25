<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'
import { useSetup } from '~/composables/auth/useSetup'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'

definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const toast = useToast()
const auth = useAuthStore()
const setup = useSetup()
const { loginWithCredentials } = useAuth()
const submitting = ref(false)

usePageSeo({
  title: () => t('pages.setup.title'),
  description: () => t('pages.setup.description'),
  robots: 'noindex, nofollow',
})

const schema = computed(() => z.object({
  name: z.string().min(1, { error: t('pages.setup.nameRequired') }),
  email: z.email({ error: t('pages.auth.emailRequired') }),
  password: z.string().min(6, { error: t('pages.auth.passwordRequired') }),
  passwordConfirmation: z.string().min(6, { error: t('pages.auth.passwordRequired') }),
}))

const fields = computed<AuthFormField[]>(() => [
  {
    name: 'name',
    type: 'text',
    size: 'lg',
    label: t('pages.setup.adminName'),
    placeholder: t('pages.setup.adminNamePlaceholder'),
    required: true,
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
  if (data.password !== data.passwordConfirmation) {
    toast.add({ title: t('pages.setup.passwordMismatch'), color: 'error' })
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
  catch {
    toast.add({ title: t('pages.setup.failed'), color: 'error' })
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      :schema="schema"
      :title="t('pages.setup.title')"
      icon="i-lucide-shield-check"
      :description="t('pages.setup.description')"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.setup.submit'),
        class: 'w-full h-10! text-xl font-normal',
        loading: submitting,
      }"
      @submit="onSubmit"
    >
      <template #leading>
        <img src="/logo.png" alt="Logo" class="mx-auto h-16 w-auto">
      </template>
    </UAuthForm>
  </div>
</template>
