<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'
import { readRememberMe, writeRememberMe } from '~/utils/auth/remember-me'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'
import { safeInternalPath } from '~/utils/auth/session'

definePageMeta({
  layout: 'auth',
})

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const { loginWithCredentials } = useAuth()
const submitting = ref(false)
const loginForm = useTemplateRef<{ state?: Record<string, unknown> }>('loginForm')

usePageSeo({
  title: () => t('pages.auth.loginTitle'),
  description: () => t('pages.auth.loginDesc'),
  robots: 'index, follow',
})

const remembered = readRememberMe()

function buildFields(): AuthFormField[] {
  return [
    {
      name: 'email',
      type: 'email',
      size: 'lg',
      label: t('pages.auth.email'),
      placeholder: t('pages.auth.emailPlaceholder'),
      required: true,
      autocomplete: 'username',
      defaultValue: remembered.email || '',
    },
    {
      name: 'password',
      type: 'password',
      size: 'lg',
      label: t('pages.auth.password'),
      placeholder: t('pages.auth.passwordPlaceholder'),
      required: true,
      autocomplete: 'current-password',
      defaultValue: '',
    },
    {
      name: 'remember',
      type: 'checkbox',
      label: t('pages.auth.remember'),
      defaultValue: remembered.enabled,
    },
  ]
}

const fields = ref<AuthFormField[]>(buildFields())

watch(locale, () => {
  fields.value = buildFields()
})

const schema = computed(() => z.object({
  email: z.email({ error: t('pages.auth.emailRequired') }),
  password: z.string().min(6, { error: t('pages.auth.passwordRequired') }),
  remember: z.boolean().optional(),
}))

type Schema = {
  email: string
  password: string
  remember?: boolean
}

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value) return

  submitting.value = true
  try {
    const formState = loginForm.value?.state || {}
    const email = String(payload.data?.email ?? formState.email ?? '').trim()
    const password = String(payload.data?.password ?? formState.password ?? '')
    const remember = Boolean(payload.data?.remember ?? formState.remember)
    const result = await loginWithCredentials(email, password, remember)
    const user = result.data?.user

    if (!user) {
      toast.add({
        title: t('pages.auth.loginFailed'),
        description: t('pages.auth.loginFailedDesc'),
        color: 'error',
      })
      return
    }

    writeRememberMe({ enabled: remember, email })
    auth.login(user)
    await router.replace(safeInternalPath(route.query.redirect) || '/')
  }
  catch {
    toast.add({
      title: t('pages.auth.loginFailed'),
      description: t('pages.auth.loginFailedDesc'),
      color: 'error',
    })
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="loginForm"
      :schema="schema"
      :title="t('pages.auth.loginTitle')"
      icon="i-lucide-lock"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.auth.loginBtn'),
        class: 'w-full h-10! text-xl font-normal',
        loading: submitting,
      }"
      @submit="onSubmit"
    >
      <template #leading>
        <img src="/logo.png" alt="Logo" class="mx-auto h-16 w-auto">
      </template>

      <template #footer>
        <div class="space-y-3">
          <div class="text-center">
            <UButton
              variant="link"
              size="sm"
              to="/auth/forget-password"
              class="text-muted-foreground underline"
            >
              {{ t('pages.auth.forgotPassword') }}
            </UButton>
          </div>
          <div class="text-center">
            <span class="text-sm font-normal text-muted">{{ $t('settings.aboutCopyright') }}</span>
          </div>
        </div>
      </template>
    </UAuthForm>
  </div>
</template>
