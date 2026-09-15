<script setup lang="ts">
import { en, km } from '@nuxt/ui/locale'
import { useSettingsRepositories } from '~/repositories'
import { useAppBranding } from '~/composables/settings/useAppBranding'
import { usePreferencesStore } from '~/stores/preferences'

const colorMode = useColorMode()
const { locale, t } = useI18n()
const { applyFromAppInfo } = useAppBranding()
const preferences = usePreferencesStore()

const uiLocales: Record<string, typeof en> = { en, km }

const color = computed(() => colorMode.value === 'dark' ? '#1b1718' : 'white')
const currentLocale = computed(() => uiLocales[locale.value] || en)
const lang = computed(() => currentLocale.value.code || locale.value)
const dir = computed(() => currentLocale.value.dir || 'ltr')
const siteName = computed(() => t('docetra.brand.name'))
const appDescription = computed(() => t('app.description'))
const appKeywords = computed(() => t('app.keywords'))
const { absoluteUrl, absolutePageUrl } = useSeoAbsoluteUrl()
const defaultOgImage = computed(() => absoluteUrl('/og-image.png'))
const pageUrl = computed(() => absolutePageUrl())

onMounted(() => {
  void preferences.hydrate()
  // Non-blocking branding hydrate — do not stall first paint
  void useSettingsRepositories().appInfo.get()
    .then(info => applyFromAppInfo(info))
    .catch(() => applyFromAppInfo(null))
})

useHead({
  // Page title only in the tab — do not append the product name again.
  titleTemplate: (titleChunk) => {
    const chunk = titleChunk?.trim()
    if (!chunk || chunk === siteName.value) return siteName.value
    return chunk
  },
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color },
    { key: 'keywords', name: 'keywords', content: appKeywords },
  ],
  link: [
    { rel: 'icon', type: 'image/png', href: '/logo.png' },
    { rel: 'apple-touch-icon', href: '/logo.png' },
  ],
  htmlAttrs: {
    lang,
    dir,
  },
})

useSeoMeta({
  description: appDescription,
  ogSiteName: siteName,
  ogTitle: siteName,
  ogDescription: appDescription,
  ogImage: () => defaultOgImage.value,
  ogImageAlt: siteName,
  ogUrl: () => pageUrl.value,
  ogType: 'website',
  twitterTitle: siteName,
  twitterDescription: appDescription,
  twitterImage: () => defaultOgImage.value,
  twitterImageAlt: siteName,
  twitterCard: 'summary_large_image',
  robots: 'noindex, nofollow',
})
</script>

<template>
  <UApp class="h-full min-h-0" :locale="currentLocale">
    <NuxtLoadingIndicator
      color="var(--ui-primary, #e8472a)"
      error-color="#ef4444"
      :height="3"
    />
    <NuxtLayout />
    <CommonAppAccessAlertHost />
    <CommonAppConfirmHost />
  </UApp>
</template>
