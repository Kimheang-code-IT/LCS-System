<script setup lang="ts">
import { useMaintenanceRepository } from '~/repositories/http/maintenance'
import type { MaintenanceStatus } from '~/types/maintenance'
definePageMeta({ layout: 'maintenance' })
const { t } = useI18n()
const repo = useMaintenanceRepository()
const status = ref<MaintenanceStatus | null>(null)
const pending = ref(false)
const error = ref('')
async function retry() {
  if (pending.value) return
  pending.value = true
  error.value = ''
  try {
    status.value = await repo.status()
    if (!status.value.active) await navigateTo('/')
  }
  catch { error.value = t('maintenance.unavailable') }
  finally { pending.value = false }
}
onMounted(() => void retry())
useHead({ title: () => t('maintenance.title') })
</script>

<template>
  <main class="flex min-h-dvh items-center justify-center bg-muted p-4 sm:p-8">
    <UCard class="w-full max-w-xl text-center">
      <img src="/lcs-invoice-logo.jpg" alt="LCS Xing Yun Logistics" class="mx-auto mb-6 h-28 w-36 object-contain">
      <UIcon name="i-lucide-wrench" class="mb-4 size-10 text-primary" />
      <h1 class="text-2xl font-semibold">{{ t('maintenance.title') }}</h1>
      <p class="mt-4 whitespace-pre-wrap break-words text-muted">{{ status?.message || t('maintenance.defaultMessage') }}</p>
      <dl class="mt-6 space-y-3 text-sm">
        <div v-if="status?.endsAt"><dt class="font-medium">{{ t('maintenance.availability') }}</dt><dd>{{ new Date(status.endsAt).toLocaleString() }}</dd></div>
        <div v-if="status?.estimatedDowntime"><dt class="font-medium">{{ t('maintenance.downtime') }}</dt><dd>{{ status.estimatedDowntime }}</dd></div>
        <div v-if="status?.supportContact"><dt class="font-medium">{{ t('maintenance.support') }}</dt><dd class="break-words">{{ status.supportContact }}</dd></div>
      </dl>
      <p v-if="error" role="alert" class="mt-4 text-error">{{ error }}</p>
      <div class="mt-8 flex flex-wrap justify-center gap-3">
        <UButton
icon="i-lucide-refresh-cw"
:loading="pending"
:label="t('maintenance.retry')"
@click="retry" />
        <UButton to="/administration/system-settings" variant="outline" :label="t('maintenance.admin')" />
        <UButton to="/auth/login" variant="ghost" :label="t('maintenance.signIn')" />
      </div>
    </UCard>
  </main>
</template>
