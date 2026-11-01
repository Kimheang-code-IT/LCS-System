<script setup lang="ts">
import { useAppHeader } from '~/composables/layout/useAppHeader'

const { displayTitle, breadcrumbs, badges, hasBreadcrumbs, actions } = useAppHeader()

/**
 * The header icon spins while the page's refresh handler actually runs.
 * Handlers either return their pending promise directly (dashboard, reports,
 * archive, document pages) or update their own `refreshing` state while
 * running (list pages), so spinning follows the real request — no simulated
 * timeouts. Awaiting the handler also serialises rapid clicks.
 */
const refreshAwaiting = ref(false)
const refreshSpinning = computed(() => Boolean(actions.value?.refreshing) || refreshAwaiting.value)

async function onHeaderRefresh() {
  const handler = actions.value?.onRefresh
  if (!handler || refreshAwaiting.value) return
  refreshAwaiting.value = true
  try {
    await handler()
  }
  catch (error) {
    // Failure feedback stays in the app's notification channels: useApi toasts
    // transport failures and pages render their own inline alerts, so the
    // header must not add a second toast (notification policy test) — it only
    // records a rejection that would otherwise vanish unhandled.
    console.error('[refresh]', error)
  }
  finally {
    refreshAwaiting.value = false
  }
}
</script>

<template>
  <UDashboardNavbar class="shrink-0 border-b border-default px-1.5">
    <template #leading>
      <UDashboardSidebarCollapse />
    </template>

    <template #title>
      <nav
        class="flex min-w-0 max-w-full items-center gap-1 overflow-hidden text-sm lg:hidden"
        :aria-label="$t('common.pages')"
      >
        <NuxtLink
          to="/"
          class="grid size-6 shrink-0 place-items-center rounded text-muted hover:bg-elevated hover:text-highlighted"
          :aria-label="$t('common.home')"
        >
          <UIcon name="i-lucide-house" class="size-4" />
        </NuxtLink>
        <UIcon name="i-lucide-chevron-right" class="size-3.5 shrink-0 text-dimmed rtl:rotate-180" />
        <span class="shrink-0 text-muted" aria-hidden="true">&hellip;</span>
        <UIcon name="i-lucide-chevron-right" class="size-3.5 shrink-0 text-dimmed rtl:rotate-180" />
        <span class="min-w-0 truncate font-medium text-highlighted">
          {{ displayTitle || 'LCS Freight' }}
        </span>
      </nav>

      <div v-if="hasBreadcrumbs" class="hidden min-w-0 max-w-full items-center gap-2 overflow-hidden lg:flex">
        <UBreadcrumb
          :items="breadcrumbs"
          color="neutral"
          class="min-w-0 truncate"
          :ui="{
            root: 'min-w-0',
            list: 'min-w-0 flex-nowrap overflow-hidden',
            link: 'text-sm',
          }"
        />
        <UBadge
          v-for="(badge, index) in badges"
          :key="`${badge.label}-${index}`"
          :color="badge.color || 'info'"
          variant="subtle"
          size="sm"
          class="shrink-0"
        >
          {{ badge.label }}
        </UBadge>
      </div>
      <span v-else class="hidden truncate text-highlighted lg:block">{{ displayTitle || 'LCS Freight' }}</span>
    </template>

    <div class="min-w-0 flex-1" />

    <template #right>
      <div class="flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2">
        <template v-if="actions?.listNav">
          <UButton
            v-if="actions.listNav.listTo"
            color="neutral"
            variant="soft"
            icon="i-lucide-list"
            :to="actions.listNav.listTo"
            :label="actions.listNav.listLabel"
            class="hidden rounded-md sm:inline-flex"
          />
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-chevron-left"
            square
            class="rounded-md"
            :loading="actions.listNav.previousLoading"
            :disabled="actions.listNav.previousDisabled"
            :aria-label="actions.listNav.previousLabel"
            @click="actions.listNav.onPrevious?.()"
          />
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-chevron-right"
            square
            class="rounded-md"
            :loading="actions.listNav.nextLoading"
            :disabled="actions.listNav.nextDisabled"
            :aria-label="actions.listNav.nextLabel"
            @click="actions.listNav.onNext?.()"
          />
        </template>

        <div
          id="app-header-leading"
          class="flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2"
        />

        <template v-if="actions">
          <CommonAppDocumentActionButton
            icon="i-lucide-refresh-cw"
            color="secondary"
            square
            :spin-icon="refreshSpinning"
            :disabled="refreshSpinning"
            :aria-label="$t('lcs.actions.refresh')"
            @click="onHeaderRefresh"
          />

          <UDropdownMenu
            v-if="actions.moreItems?.length"
            :items="actions.moreItems"
            :content="{ align: 'end' }"
          >
            <CommonAppDocumentActionButton
              icon="i-lucide-ellipsis"
              color="secondary"
              square
              :aria-label="$t('common.moreActions')"
            />
          </UDropdownMenu>
        </template>

        <div
          id="app-header-trailing"
          class="flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2"
        />

        <CommonAppDocumentActionButton
          v-if="actions?.cancel?.to"
          color="secondary"
          :to="actions.cancel.to"
          :label="actions.cancel.label"
        />
        <CommonAppDocumentActionButton
          v-else-if="actions?.cancel"
          color="secondary"
          :label="actions.cancel.label"
          @click="actions.cancel.onClick?.()"
        />
        <CommonAppDocumentActionButton
          v-if="actions?.save"
          icon="i-lucide-save"
          :label="actions.save.label"
          :loading="actions.save.loading"
          @click="actions.save.onClick()"
        />

        <template v-if="actions?.createButtons?.length">
          <CommonAppDocumentActionButton
            v-for="(button, index) in actions.createButtons"
            :key="`${button.label}-${index}`"
            :icon="button.icon || 'i-lucide-plus'"
            :label="button.label"
            @click="button.onClick()"
          />
        </template>
        <CommonAppDocumentActionButton
          v-else-if="actions?.canCreate"
          :icon="actions.createIcon || 'i-lucide-plus'"
          :label="actions.createLabel"
          @click="actions.onCreate?.()"
        />
      </div>
    </template>
  </UDashboardNavbar>
</template>
