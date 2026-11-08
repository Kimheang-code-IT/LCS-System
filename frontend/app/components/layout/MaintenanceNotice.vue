<script setup lang="ts">
import { useMaintenanceRepository } from '~/repositories/http/maintenance'
import type { MaintenanceStatus } from '~/types/maintenance'
const repo = useMaintenanceRepository()
const { t } = useI18n()
const route = useRoute()
const status = ref<MaintenanceStatus | null>(null)
let timer: ReturnType<typeof setInterval> | undefined
let pending = false
async function refresh() {
  if (pending) return
  pending = true
  try {
    status.value = await repo.status()
    if (status.value.active && route.path !== '/administration/system-settings') await navigateTo('/maintenance')
  }
  catch { /* Admission remains enforced by the backend while status is unavailable. */ }
  finally { pending = false }
}
onMounted(() => { void refresh(); timer = setInterval(() => void refresh(), 30000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <UAlert
v-if="status?.active || status?.scheduled"
color="warning"
icon="i-lucide-wrench"
:title="status.active ? t('maintenance.active') : t('maintenance.scheduledNotice', { time: status.startsAt ? new Date(status.startsAt).toLocaleString() : '' })"
class="shrink-0 rounded-none" />
</template>
