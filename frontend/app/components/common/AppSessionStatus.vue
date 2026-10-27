<script setup lang="ts">
const auth = useAuthStore()
const { t } = useI18n()
const route = useRoute()
const loginUrl = computed(() => `/auth/login?redirect=${encodeURIComponent(route.fullPath)}`)
</script>

<template>
  <div
    v-if="(auth.sessionExpired || auth.connectionProblem || auth.logoutFailed) && !route.path.startsWith('/auth/')"
    class="fixed inset-x-0 top-0 z-[100] flex items-center justify-center gap-3 border-b border-warning bg-default p-3 text-sm"
    role="alert"
  >
    <span>{{ t(auth.logoutFailed ? 'session.logoutFailed' : auth.accountChanged ? 'session.accountChanged' : auth.sessionExpired ? 'session.expired' : 'session.connection') }}</span>
    <UButton v-if="auth.logoutFailed" size="sm" @click="auth.logout()">{{ t('session.retry') }}</UButton>
    <UButton
v-else-if="auth.sessionExpired"
:to="loginUrl"
target="_blank"
size="sm">{{ t('session.signIn') }}</UButton>
    <UButton v-else size="sm" @click="auth.renewAccess()">{{ t('session.retry') }}</UButton>
  </div>
</template>
