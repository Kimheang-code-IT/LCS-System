<script setup lang="ts">
import { useAppHeader } from '~/composables/layout/useAppHeader'

const { displayTitle, breadcrumbs, badges, hasBreadcrumbs, actions } = useAppHeader()

/** Spin on every click — page `refreshing` alone misses synchronous refreshes. */
const refreshSpin = ref(false)
let refreshSpinTimer: ReturnType<typeof setTimeout> | null = null
const refreshSpinning = computed(() => Boolean(actions.value?.refreshing) || refreshSpin.value)

function onHeaderRefresh() {
  const handler = actions.value?.onRefresh
  if (!handler) return
  if (refreshSpinTimer) clearTimeout(refreshSpinTimer)
  refreshSpin.value = true
  try {
    handler()
  }
  finally {
    refreshSpinTimer = setTimeout(() => {
      refreshSpin.value = false
    }, 450)
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
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-refresh-cw"
            square
            :class="refreshSpinning ? 'animate-spin' : ''"
            :disabled="refreshSpinning"
            class="rounded-md"
            :aria-label="$t('docetra.actions.refresh')"
            @click="onHeaderRefresh"
          />

          <UDropdownMenu
            v-if="actions.moreItems?.length"
            :items="actions.moreItems"
            :content="{ align: 'end' }"
          >
            <UButton
              color="neutral"
              variant="soft"
              icon="i-lucide-ellipsis"
              square
              class="rounded-md"
              :aria-label="$t('common.actions')"
            />
          </UDropdownMenu>
        </template>

        <div
          id="app-header-trailing"
          class="flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2"
        />

        <UButton
          v-if="actions?.metaRail"
          :icon="actions.metaRail.open ? 'i-lucide-panel-right-close' : 'i-lucide-panel-right-open'"
          color="neutral"
          variant="soft"
          square
          class="rounded-md"
          :aria-label="actions.metaRail.label"
          :aria-expanded="actions.metaRail.open"
          @click="actions.metaRail.onToggle()"
        />

        <UButton
          v-if="actions?.cancel?.to"
          color="neutral"
          variant="ghost"
          :to="actions.cancel.to"
          :label="actions.cancel.label"
          class="rounded-md"
        />
        <UButton
          v-else-if="actions?.cancel"
          color="neutral"
          variant="ghost"
          :label="actions.cancel.label"
          class="rounded-md"
          @click="actions.cancel.onClick?.()"
        />
        <UButton
          v-if="actions?.save"
          :loading="actions.save.loading"
          icon="i-lucide-save"
          :label="actions.save.label"
          class="rounded-md"
          @click="actions.save.onClick()"
        />

        <template v-if="actions?.createButtons?.length">
          <UButton
            v-for="(button, index) in actions.createButtons"
            :key="`${button.label}-${index}`"
            color="neutral"
            variant="solid"
            :icon="button.icon || 'i-lucide-plus'"
            :label="button.label"
            class="rounded-md"
            @click="button.onClick()"
          />
        </template>
        <UButton
          v-else-if="actions?.canCreate"
          color="neutral"
          variant="solid"
          :icon="actions.createIcon || 'i-lucide-plus'"
          :label="actions.createLabel"
          class="rounded-md"
          @click="actions.onCreate?.()"
        />
      </div>
    </template>
  </UDashboardNavbar>
</template>
