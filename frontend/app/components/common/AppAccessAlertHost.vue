<script setup lang="ts">
import { useAccessAlert } from '~/composables/common/useAccessAlert'

const { state, close } = useAccessAlert()
const { t } = useI18n()

const isSessionExpired = computed(() => state.value.kind === 'session-expired')
const title = computed(() => isSessionExpired.value
  ? t('docetra.states.sessionExpiredTitle')
  : t('docetra.states.accessDeniedTitle'))
const description = computed(() => state.value.description || (isSessionExpired.value
  ? t('docetra.states.sessionExpiredDescription')
  : t('docetra.states.accessDeniedDescription')))
const actionLabel = computed(() => isSessionExpired.value
  ? t('docetra.states.signInAgain')
  : t('docetra.common.ok'))

const open = computed({
  get: () => state.value.open,
  set: (value: boolean) => {
    if (!value) close()
  },
})

function acknowledge() {
  close()
  if (isSessionExpired.value) void navigateTo('/auth/login')
}
</script>

<template>
  <UModal v-model:open="open" :dismissible="false" :ui="{ overlay: 'z-[250]', content: 'z-[250]' }">
    <template #content>
      <UCard>
        <div class="flex items-start gap-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-full"
            :class="isSessionExpired ? 'bg-warning/10 text-warning' : 'bg-error/10 text-error'"
          >
            <UIcon
              :name="isSessionExpired ? 'i-lucide-clock-alert' : 'i-lucide-shield-alert'"
              class="size-5"
            />
          </div>

          <div class="min-w-0 flex-1">
            <h3 class="text-base font-semibold text-highlighted">{{ title }}</h3>
            <p class="mt-1 text-sm text-muted">{{ description }}</p>

            <dl v-if="!isSessionExpired && (state.requestedPath || state.permission)" class="mt-4 space-y-2 rounded-lg bg-elevated/60 p-3 text-xs">
              <div v-if="state.requestedPath" class="grid gap-1 sm:grid-cols-[9rem_1fr]">
                <dt class="font-medium text-muted">{{ $t('docetra.states.requestedPage') }}</dt>
                <dd class="break-all text-highlighted">{{ state.requestedPath }}</dd>
              </div>
              <div v-if="state.permission" class="grid gap-1 sm:grid-cols-[9rem_1fr]">
                <dt class="font-medium text-muted">{{ $t('docetra.states.requiredPermission') }}</dt>
                <dd class="break-all font-mono text-highlighted">{{ state.permission }}</dd>
              </div>
            </dl>
          </div>
        </div>

        <template #footer>
          <div class="flex justify-end">
            <UButton :color="isSessionExpired ? 'warning' : 'error'" @click="acknowledge">
              {{ actionLabel }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
