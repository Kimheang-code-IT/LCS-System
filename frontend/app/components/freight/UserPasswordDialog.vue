<script setup lang="ts">
/**
 * Set a password on another account, and hand a newly created one over.
 *
 * One component serves both jobs because they differ only in framing: an
 * administrator either chooses a password for an existing account, or needs to
 * see the one they just typed for a new account before it leaves the screen.
 *
 * What it deliberately cannot do is show an existing password. The server stores
 * an Argon2id digest, so there is nothing to reveal; a reset is the only way to
 * give somebody access.
 *
 * Errors follow the shared policy: field problems render under the field, a
 * refused request renders as a form-level message, and only a confirmed success
 * raises a toast.
 */
import { apiErrorMessage, normalizeApiError } from '~/utils/validation/api-error'
import { generateStrongPassword, validatePasswordStrength } from '~/utils/validation/field-rules'
import { issueMessage } from '~/utils/validation/messages'
import { useLcsRepositories } from '~/repositories'

const props = withDefaults(defineProps<{
  open: boolean
  /** Account being changed; omitted in handover mode. */
  userId?: string
  userLabel?: string
  /** Show the password that was just set instead of a form to choose one. */
  mode?: 'set' | 'handover'
  /** The password to display in handover mode. */
  revealedPassword?: string
}>(), {
  userId: '',
  userLabel: '',
  mode: 'set',
  revealedPassword: '',
})

const emit = defineEmits<{
  'update:open': [boolean]
  /** Fired after the server confirmed the new password. */
  saved: [string]
}>()

const { t } = useI18n()
const { users } = useLcsRepositories()

const password = ref('')
const confirmation = ref('')
const mustChangePassword = ref(true)
const submitting = ref(false)
const copied = ref(false)
const fieldErrors = ref<Record<string, string>>({})
const formError = ref('')

const isHandover = computed(() => props.mode === 'handover')

function useGenerated() {
  password.value = generateStrongPassword()
  confirmation.value = password.value
  fieldErrors.value = {}
}

async function copy(value: string) {
  copied.value = false
  try {
    await navigator.clipboard.writeText(value)
    copied.value = true
  }
  catch {
    // Clipboard access can be denied by the browser. The text is on screen, so
    // this is a hint rather than a failure and must not be a toast.
    copied.value = false
  }
}

function validate(): boolean {
  const errors: Record<string, string> = {}
  const issue = validatePasswordStrength(password.value)
  if (issue) {
    errors.password = issueMessage(t, issue, t('freight.users.password.newPassword'))
  }
  else if (confirmation.value !== password.value) {
    errors.passwordConfirmation = t('validation.passwordMismatch')
  }
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit() {
  if (isHandover.value) return close()
  if (!validate()) return
  submitting.value = true
  formError.value = ''
  try {
    await users.setPassword(String(props.userId), password.value, {
      mustChangePassword: mustChangePassword.value,
    })
    emit('saved', password.value)
    close()
  }
  catch (error) {
    // A field-level refusal from the server lands under the field; anything else
    // is a form-level message. Neither is a toast.
    const normalized = normalizeApiError(error)
    if (Object.keys(normalized.fieldErrors ?? {}).length) {
      fieldErrors.value = { ...fieldErrors.value, ...normalized.fieldErrors }
    }
    else {
      formError.value = apiErrorMessage(error, t('freight.ui.saveFailed'))
    }
  }
  finally {
    submitting.value = false
  }
}

function close() {
  emit('update:open', false)
  password.value = ''
  confirmation.value = ''
  mustChangePassword.value = true
  fieldErrors.value = {}
  formError.value = ''
  copied.value = false
}

// Reset the form whenever the dialog is opened for a different account.
watch(() => [props.open, props.userId], () => {
  if (props.open && !isHandover.value) {
    password.value = ''
    confirmation.value = ''
    mustChangePassword.value = true
    fieldErrors.value = {}
    formError.value = ''
  }
})
</script>

<template>
  <UModal
    :open="open"
    :title="isHandover
      ? t('freight.users.password.handoverTitle')
      : t('freight.users.password.title')"
    :description="isHandover
      ? t('freight.users.password.handoverDescription', { user: userLabel })
      : t('freight.users.password.description', { user: userLabel })"
    @update:open="emit('update:open', $event)">
    <template #body>
      <div v-if="isHandover" class="space-y-4">
        <div class="flex items-center gap-2">
          <UInput
            :model-value="revealedPassword"
            type="text"
            readonly
            size="md"
            class="w-full font-mono"
            :aria-label="t('freight.users.password.newPassword')" />
          <UButton
            :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
            color="neutral"
            variant="subtle"
            :aria-label="t('freight.users.password.copy')"
            @click="copy(revealedPassword)" />
        </div>
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('freight.users.password.handoverWarning')" />
      </div>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <CommonAppFormErrorSummary v-if="formError" :form-errors="[formError]" />

        <CommonAppSecretInput
          v-model="password"
          :label="t('freight.users.password.newPassword')"
          :help="t('freight.users.password.requirements')"
          autocomplete="new-password"
          data-field-key="password" />
        <p v-if="fieldErrors.password" class="text-xs text-error" role="alert">
          {{ fieldErrors.password }}
        </p>

        <CommonAppSecretInput
          v-model="confirmation"
          :label="t('freight.users.password.confirmPassword')"
          autocomplete="new-password"
          data-field-key="passwordConfirmation" />
        <p v-if="fieldErrors.passwordConfirmation" class="text-xs text-error" role="alert">
          {{ fieldErrors.passwordConfirmation }}
        </p>

        <UButton
          icon="i-lucide-dice-5"
          color="neutral"
          variant="subtle"
          type="button"
          :label="t('freight.users.password.generate')"
          @click="useGenerated" />

        <UCheckbox
          v-model="mustChangePassword"
          :label="t('freight.users.password.requireChange')"
          :help="t('freight.users.password.requireChangeHelp')" />
      </form>
    </template>

    <template #footer>
      <div class="flex w-full items-center justify-end gap-2">
        <UButton
          :label="isHandover ? t('lcs.common.close') : t('lcs.common.cancel')"
          color="neutral"
          variant="ghost"
          @click="close" />
        <UButton
          v-if="!isHandover"
          :label="t('freight.users.password.submit')"
          :loading="submitting"
          :disabled="submitting"
          @click="submit" />
      </div>
    </template>
  </UModal>
</template>
