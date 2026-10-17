<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { useAuth } from '~/composables/auth/useAuth'
import { useAuthStore } from '~/stores/auth'
import { apiErrorMessage, normalizeApiError } from '~/utils/validation/api-error'
import { resolveUserAvatar } from '~/utils/auth/user-avatar'

const open = defineModel<boolean>('open', { default: false })

const auth = useAuthStore()
const { changePassword, removeProfileAvatar, updateProfileAvatar } = useAuth()
const { t } = useI18n()
const toast = useToast()

const submitting = ref(false)
const avatarSubmitting = ref(false)
const avatarInputRef = ref<HTMLInputElement | null>(null)
const photoPreviewOpen = ref(false)
/**
 * Rejections are shown next to the control they belong to, never as a toast:
 * `avatarError` for the photo control, `passwordError` for the password form.
 */
const avatarError = ref('')
const passwordError = ref('')
const passwordForm = useTemplateRef<{
  formRef?: { setErrors: (errors: Array<{ name: string, message: string }>) => void, clear: () => void }
} | null>('passwordForm')

const profile = computed(() => {
  const user = auth.user
  return {
    name: user?.name || t('lcs.userProfile.unknownUser'),
    email: user?.email || '—',
    role: user?.role || t('lcs.userProfile.noRole'),
    avatar: {
      src: resolveUserAvatar(user),
      alt: user?.name || 'User',
    },
  }
})

const hasCustomAvatar = computed(() => Boolean(auth.user?.avatar))

const passwordSchema = computed(() => z.object({
  currentPassword: z.string().min(1, { error: t('lcs.userProfile.currentPasswordRequired') }),
  password: z.string().min(8, { error: t('pages.forgetPassword.passwordMin') }).max(20, { error: t('pages.forgetPassword.passwordMax') }),
  passwordConfirmation: z.string().min(8, { error: t('pages.forgetPassword.passwordMin') }).max(20, { error: t('pages.forgetPassword.passwordMax') }),
}).refine(data => data.password === data.passwordConfirmation, {
  message: t('pages.forgetPassword.passwordMismatch'),
  path: ['passwordConfirmation'],
}))

type PasswordSchema = z.infer<typeof passwordSchema.value>

const passwordState = reactive({
  currentPassword: '',
  password: '',
  passwordConfirmation: '',
})

watch(open, (isOpen) => {
  if (!isOpen) {
    photoPreviewOpen.value = false
    passwordState.currentPassword = ''
    passwordState.password = ''
    passwordState.passwordConfirmation = ''
  }
})

function openAvatarPicker() {
  if (avatarSubmitting.value) return
  avatarInputRef.value?.click()
}

function openPhotoPreview() {
  if (avatarSubmitting.value) return
  photoPreviewOpen.value = true
}

function onCameraClick(event: Event) {
  event.stopPropagation()
  openAvatarPicker()
}

async function onAvatarPick(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || avatarSubmitting.value) return

  if (!SAFE_RASTER_IMAGE_TYPES.includes(file.type as (typeof SAFE_RASTER_IMAGE_TYPES)[number])) {
    avatarError.value = t('lcs.common.imageInvalidType')
    return
  }
  if (!isSafeRasterImage(file, 2)) {
    avatarError.value = t('lcs.common.imageTooLarge', { size: 2 })
    return
  }

  avatarError.value = ''
  avatarSubmitting.value = true
  try {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('read failed'))
      reader.readAsDataURL(file)
    })
    await updateProfileAvatar(dataUrl)
    photoPreviewOpen.value = true
    toast.add({
      title: t('lcs.userProfile.photoUpdated'),
      description: t('lcs.userProfile.photoUpdatedDesc'),
      color: 'success',
    })
  }
  catch (error) {
    avatarError.value = apiErrorMessage(error, t('lcs.userProfile.photoUpdateFailed'))
  }
  finally {
    avatarSubmitting.value = false
  }
}

async function onRemoveAvatar() {
  if (avatarSubmitting.value || !hasCustomAvatar.value) return
  avatarError.value = ''
  avatarSubmitting.value = true
  try {
    await removeProfileAvatar()
    photoPreviewOpen.value = false
    toast.add({
      title: t('lcs.userProfile.photoRemoved'),
      description: t('lcs.userProfile.photoRemovedDesc'),
      color: 'success',
    })
  }
  catch (error) {
    avatarError.value = apiErrorMessage(error, t('lcs.userProfile.photoRemoveFailed'))
  }
  finally {
    avatarSubmitting.value = false
  }
}

async function onPasswordSubmit(event: FormSubmitEvent<PasswordSchema>) {
  if (submitting.value) return
  submitting.value = true
  passwordError.value = ''
  passwordForm.value?.formRef?.clear()
  try {
    await changePassword({
      currentPassword: event.data.currentPassword,
      password: event.data.password,
      passwordConfirmation: event.data.passwordConfirmation,
    })
    toast.add({
      title: t('lcs.userProfile.passwordChanged'),
      description: t('lcs.userProfile.passwordChangedDesc'),
      color: 'success',
    })
    passwordState.currentPassword = ''
    passwordState.password = ''
    passwordState.passwordConfirmation = ''
  }
  catch (error) {
    // A wrong current password belongs on that input; anything else is a
    // form-level notice directly above the form.
    const entries = Object.entries(normalizeApiError(error).fieldErrors)
      .filter(([name, message]) => name in passwordState && message)
      .map(([name, message]) => ({ name, message }))
    if (entries.length) passwordForm.value?.formRef?.setErrors(entries)
    else passwordError.value = apiErrorMessage(error, t('lcs.userProfile.passwordChangeFailed'))
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    scrollable
    :title="t('lcs.userProfile.title')"
    :dismissible="false"
    :close="{ color: 'primary', variant: 'outline', class: 'rounded-full' }"
    :ui="{
      overlay: 'place-items-start justify-items-center pt-[5vh] sm:pt-[5vh]',
      content: 'w-[calc(100%-2rem)] max-w-2xl sm:max-w-2xl',
    }"
  >
    <template #body>
      <div class="space-y-5">
        <div class="flex flex-col items-center gap-4 pb-1 text-center">
          <div class="relative inline-flex">
            <button
              type="button"
              class="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              :aria-label="t('lcs.userProfile.viewPhoto')"
              @click="openPhotoPreview"
            >
              <img
                :src="profile.avatar.src"
                :alt="profile.avatar.alt"
                class="size-16 rounded-full object-cover ring-2 ring-default sm:size-20"
                referrerpolicy="no-referrer"
              >
            </button>
            <span
              class="absolute -inset-e-2 -top-2 z-10 max-w-[6.5rem] truncate rounded-full bg-elevated px-2 py-0.5 text-[10px] font-semibold leading-none text-toned ring-1 ring-default shadow-sm"
              :title="profile.role"
            >
              {{ profile.role }}
            </span>
            <button
              type="button"
              class="absolute -bottom-1 -end-1 z-10 inline-flex size-7 items-center justify-center rounded-full border-2 border-default bg-default text-highlighted shadow-sm transition hover:bg-elevated disabled:opacity-60"
              :aria-label="t('lcs.userProfile.changePhoto')"
              :disabled="avatarSubmitting"
              @click="onCameraClick"
            >
              <UIcon
                :name="avatarSubmitting ? 'i-lucide-loader-circle' : 'i-lucide-camera'"
                class="size-4"
                :class="avatarSubmitting ? 'animate-spin' : ''"
              />
            </button>
            <input
              ref="avatarInputRef"
              type="file"
              class="hidden"
              :accept="SAFE_RASTER_IMAGE_ACCEPT"
              @change="onAvatarPick"
            >
          <p
              v-if="avatarError"
              class="flex items-start gap-1.5 text-sm text-error"
              role="alert"
            >
              <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>{{ avatarError }}</span>
            </p>
          </div>
          <div class="min-w-0 max-w-full space-y-1">
            <h3 class="truncate text-lg font-semibold text-highlighted sm:text-xl">
              {{ profile.name }}
            </h3>
            <p class="truncate text-sm text-muted">
              {{ profile.email }}
            </p>
          </div>
        </div>

        <div class="space-y-4 border-t border-default pt-4">
          <h4 class="text-sm font-semibold text-highlighted">
            {{ t('lcs.userProfile.tabs.password') }}
          </h4>

          <p
            v-if="passwordError"
            class="flex items-start gap-1.5 text-sm text-error"
            role="alert"
          >
            <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{{ passwordError }}</span>
          </p>

          <UForm
            ref="passwordForm"
            :schema="passwordSchema"
            :state="passwordState"
            class="space-y-4"
            @submit="onPasswordSubmit"
          >
            <UFormField
              :label="t('lcs.userProfile.currentPassword')"
              name="currentPassword"
              required
              :help="t('lcs.userProfile.currentPasswordHelp')"
            >
              <UInput
                v-model="passwordState.currentPassword"
                type="password"
                autocomplete="current-password"
                class="w-full"
              />
            </UFormField>

            <UFormField
              :label="t('pages.forgetPassword.newPassword')"
              name="password"
              required
              :help="t('lcs.userProfile.newPasswordHelp')"
            >
              <UInput
                v-model="passwordState.password"
                type="password"
                autocomplete="new-password"
                class="w-full"
              />
            </UFormField>

            <UFormField
              :label="t('pages.forgetPassword.confirmPassword')"
              name="passwordConfirmation"
              required
              :help="t('lcs.userProfile.confirmPasswordHelp')"
            >
              <UInput
                v-model="passwordState.passwordConfirmation"
                type="password"
                autocomplete="new-password"
                class="w-full"
              />
            </UFormField>

            <div class="flex justify-end pt-1">
              <UButton
                type="submit"
                color="primary"
                :loading="submitting"
              >
                {{ t('lcs.userProfile.updatePassword') }}
              </UButton>
            </div>
          </UForm>
        </div>
      </div>
    </template>
  </UModal>

  <UModal
    v-model:open="photoPreviewOpen"
    :title="profile.name"
    :dismissible="false"
    :close="{ color: 'primary', variant: 'outline', class: 'rounded-full' }"
    :ui="{
      overlay: 'place-items-center justify-items-center',
      content: 'w-[calc(100%-2rem)] max-w-lg sm:max-w-2xl',
    }"
  >
    <template #body>
      <div class="relative overflow-hidden rounded-xl border border-default bg-elevated/30">
        <img
          :src="profile.avatar.src"
          :alt="profile.avatar.alt"
          class="mx-auto max-h-[min(80vh,36rem)] w-full object-contain"
          referrerpolicy="no-referrer"
        >
        <button
          v-if="hasCustomAvatar"
          type="button"
          class="absolute top-2 end-2 inline-flex size-9 items-center justify-center rounded-full bg-error text-white shadow-md transition hover:bg-error/90 disabled:opacity-60"
          :aria-label="t('lcs.userProfile.removePhoto')"
          :disabled="avatarSubmitting"
          @click="onRemoveAvatar"
        >
          <UIcon
            :name="avatarSubmitting ? 'i-lucide-loader-circle' : 'i-lucide-trash-2'"
            class="size-4"
            :class="avatarSubmitting ? 'animate-spin' : ''"
          />
        </button>
      </div>
    </template>
  </UModal>
</template>
