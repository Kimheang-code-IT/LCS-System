<script setup lang="ts">
import type { NuxtError } from '#app'
import { usePageSeo } from '~/composables/usePageSeo'

const props = defineProps<{
  error: NuxtError
}>()

const { locale, t } = useI18n()
const isNotFound = computed(() => props.error.statusCode === 404)
const title = computed(() => t(isNotFound.value ? 'pages.error.title' : 'pages.error.unexpectedTitle'))
const description = computed(() => t(isNotFound.value ? 'pages.error.description' : 'pages.error.unexpectedDescription'))
const statusCode = computed(() => Number.isInteger(props.error.statusCode) ? props.error.statusCode : 500)

onMounted(() => console.error('Unhandled application error', props.error))

usePageSeo({
  title,
  description,
  robots: 'noindex, nofollow',
})

useHead({
  htmlAttrs: {
    lang: locale
  }
})
</script>

<template>
  <UApp>
    <main class="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p class="text-sm font-semibold text-primary">{{ statusCode }}</p>
      <h1 class="text-2xl font-semibold text-highlighted">{{ title }}</h1>
      <p class="max-w-lg text-muted">{{ description }}</p>
      <UButton
        icon="i-lucide-house"
        :label="t('pages.error.backHome')"
        @click="clearError({ redirect: '/' })"
      />
    </main>
  </UApp>
</template>
