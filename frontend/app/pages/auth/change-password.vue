<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { useAuth } from '~/composables/auth/useAuth'
import { usePageSeo } from '~/composables/usePageSeo'
import { apiErrorDetails } from '~/utils/freight/errors'
import { PASSWORD_MAX_LENGTH, validatePasswordStrength } from '~/utils/validation/field-rules'
import { passwordIssueMessage, strongPasswordSchema } from '~/utils/validation/password-schema'

/**
 * Where a session lands when an administrator chose its password.
 *
 * The API refuses every other route while `must_change_password` stands, so this
 * screen is not a suggestion: it is the only thing the session can do besides
 * signing out. On success the server revokes every session, so the user signs in
 * again with the password they just chose.
 */
definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const { changePassword } = useAuth()
const submitting = ref(false)
const formError = ref('')
const passwordForm = useTemplateRef<{
  formRef?: {
    setErrors: (errors: { name: string, message: string }[]) => void
    clear: () => void
  }
  /** Exposed by UAuthForm; the source of truth for the live checklist and gate. */
  state?: { currentPassword: string, password: string, passwordConfirmation: string }
}>('passwordForm')

 /**
  * `UAuthForm`'s `#<name>-help` slot re-exports its content without props, so
  * the checklist binds to the exposed reactive `state` — the same source the
  * submit gate reads — instead of an empty slot payload.
  */
const password = computed(() => passwordForm.value?.state?.password ?? '')

/**
 * The submit button is disabled while a rule fails, so without these the reason
 * would never be visible: they render the shared policy message under the
 * password field (and the mismatch under the confirmation field) while typing.
 * Both stay empty on fresh fields so the form does not scold untouched inputs.
 */
const passwordHint = computed(() => {
  const state = passwordForm.value?.state
  return state?.password
    ? passwordIssueMessage(t, state.password, t('pages.changePassword.newPassword'))
    : ''
})

const confirmationHint = computed(() => {
  const state = passwordForm.value?.state
  return state?.passwordConfirmation
    && state.password !== state.passwordConfirmation
    ? t('validation.passwordMismatch')
    : ''
})

/** Enter, or the submit button, is refused until every rule and the match pass. */
const passwordsValid = computed(() => {
  const state = passwordForm.value?.state
  return Boolean(
    state
    && !validatePasswordStrength(state.password)
    && state.password === state.passwordConfirmation,
  )
})

/** Errors are placed on the field they belong to, or just above the submit button. */
function clearErrors() {
  formError.value = ''
  passwordForm.value?.formRef?.clear()
}

function showErrors(error: unknown, fallback: string) {
  const { message, fieldErrors } = apiErrorDetails(error)
  const known = ['currentPassword', 'current_password', 'password', 'passwordConfirmation', 'password_confirmation']
  const entries = Object.entries(fieldErrors || {})
    .filter(([name, text]) => known.includes(name) && text)
    .map(([name, text]) => ({ name: name.replace(/_(\w)/g, (_, c: string) => c.toUpperCase()), message: text }))
  formError.value = ''
  if (entries.length) {
    passwordForm.value?.formRef?.setErrors(entries)
    return
  }
  formError.value = message || fallback
}

usePageSeo({
  title: () => t('pages.changePassword.title'),
  description: () => t('pages.changePassword.description'),
  robots: 'noindex, nofollow',
})

const schema = computed(() => z.object({
  currentPassword: z.string().min(1, { error: t('pages.changePassword.currentRequired') }).max(PASSWORD_MAX_LENGTH),
  password: strongPasswordSchema(t, t('pages.changePassword.newPassword')),
  passwordConfirmation: z.string()
    .min(1, { error: t('validation.required', { field: t('pages.changePassword.confirmPassword') }) })
    .max(PASSWORD_MAX_LENGTH),
}).refine(data => data.password === data.passwordConfirmation, {
  message: t('validation.passwordMismatch'),
  path: ['passwordConfirmation'],
}))

const fields = computed(() => [
  {
    name: 'currentPassword',
    type: 'password' as const,
    size: 'lg' as const,
    label: t('pages.changePassword.currentPassword'),
    placeholder: t('pages.changePassword.currentPasswordPlaceholder'),
    required: true,
    autocomplete: 'current-password',
  },
  {
    name: 'password',
    type: 'password' as const,
    size: 'lg' as const,
    label: t('pages.changePassword.newPassword'),
    placeholder: t('pages.changePassword.newPasswordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
  {
    name: 'passwordConfirmation',
    type: 'password' as const,
    size: 'lg' as const,
    label: t('pages.changePassword.confirmPassword'),
    placeholder: t('pages.changePassword.confirmPasswordPlaceholder'),
    required: true,
    autocomplete: 'new-password',
  },
])

type Schema = {
  currentPassword: string
  password: string
  passwordConfirmation: string
}

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value || !passwordsValid.value) return
  clearErrors()
  submitting.value = true
  try {
    await changePassword({
      currentPassword: payload.data.currentPassword,
      password: payload.data.password,
      passwordConfirmation: payload.data.passwordConfirmation,
    })
    // The change revokes every session including this one, so the only honest
    // next step is to sign in again with the password just chosen.
    toast.add({
      title: t('pages.changePassword.success'),
      description: t('pages.changePassword.successDescription'),
      color: 'success',
    })
    auth.clearSession()
    await router.push('/auth/login')
  }
  catch (error) {
    showErrors(error, t('pages.changePassword.failed'))
  }
  finally {
    submitting.value = false
  }
}

async function signOut() {
  await auth.logout()
  await router.push('/auth/login')
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="passwordForm"
      :schema="schema"
      :title="t('pages.changePassword.title')"
      icon="i-lucide-shield-alert"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.changePassword.submit'),
        class: 'w-full h-10! text-xl font-normal',
        loading: submitting,
        disabled: !passwordsValid || submitting,
      }"
      @submit="onSubmit"
    >
      <template #password-help>
        <CommonAppPasswordRequirements :value="password" />
        <p v-if="passwordHint" class="mt-1 text-xs text-error" role="alert">
          {{ passwordHint }}
        </p>
      </template>
      <template #passwordConfirmation-help>
        <p v-if="confirmationHint" class="text-xs text-error" role="alert">
          {{ confirmationHint }}
        </p>
      </template>
      <template #leading>
        <img src="/logo.png" alt="Logo" class="mx-auto h-20 w-auto">
      </template>

      <template #description>
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('pages.changePassword.notice')" />
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
            class="text-muted-foreground underline"
            @click="signOut">
            <UIcon name="i-lucide-log-out" class="mr-1" />
            {{ t('pages.changePassword.signOut') }}
          </UButton>
          <div>
            <span class="text-sm font-normal text-muted">{{ $t('settings.aboutCopyright') }}</span>
          </div>
        </div>
      </template>
    </UAuthForm>
  </div>
</template>