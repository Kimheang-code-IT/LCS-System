<script setup lang="ts">
import type { ComponentTabRuntime, ConfigurationVersion } from '~/types/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { userSourcePermissions } from '~/utils/freight/permissions'
import { snapshotPreviewTabs } from '~/utils/freight/config-version-preview'
import { apiErrorMessage } from '~/utils/validation/api-error'

definePageMeta({
  titleKey: 'freight.pages.configurationVersions',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const config = useComponentConfig()
const auth = useAuthStore()

const name = ref('')
const pageErrors = ref<string[]>([])

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: key => (key === 'changeNote' ? 'Name' : key),
  order: () => ['changeNote'],
})

const permissionCodes = computed(() => new Set<string>(userSourcePermissions(auth.user)))
const pageKeys = computed(() => new Set(auth.user?.pageAccess || auth.user?.permissions || []))
const canPublish = computed(() =>
  permissionCodes.value.has('configuration.publish')
  || permissionCodes.value.has('configuration.manage')
  || pageKeys.value.has('configuration.edit'),
)

const live = computed(() => config.preview.value)
const active = computed(() => config.activeVersion.value)
const previewTabs = computed<ComponentTabRuntime[]>(() =>
  live.value ? snapshotPreviewTabs({ configSnapshot: live.value.preview } as unknown as ConfigurationVersion) : [],
)
const canSave = computed(() =>
  canPublish.value
  && live.value !== null
  && live.value.tabCount > 0
  && !live.value.unchanged
  && !config.saving.value,
)

const groupCount = computed(() => previewTabs.value.reduce((total, tab) => total + (tab.groups?.length || 0), 0))
const fieldCount = computed(() => previewTabs.value.reduce(
  (total, tab) => total + (tab.groups || []).reduce((sum, group) => sum + (group.attributes?.length || 0), 0),
  0,
))

async function load() {
  pageErrors.value = []
  try {
    await Promise.all([config.loadConfigurationPreview(), config.loadActiveConfigurationVersion()])
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

async function save() {
  validation.reset()
  const note = name.value.trim()
  if (!note) {
    validation.setFieldError('changeNote', validation.message({ code: 'required' }, 'Name'))
    void validation.focusFirstInvalid()
    return
  }
  if (!canSave.value) return
  try {
    const published = await config.publishConfiguration(note)
    toast.add({ title: t('freight.configVersions.published'), color: 'success' })
    await navigateTo(`/configuration/versions/${published.id}`)
  }
  catch (error) {
    validation.applyServerError(error)
    void validation.focusFirstInvalid()
  }
}

onMounted(load)
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      show-list-nav
      list-to="/configuration/versions"
      :is-create="true"
      :refreshing="config.loading.value"
      :show-save="canSave"
      :save-label="t('freight.configVersions.publish')"
      :saving="config.saving.value"
      show-cancel
      cancel-to="/configuration/versions"
      @refresh="load"
      @save="save"
    />

    <div class="min-h-0 flex-1 overflow-y-auto p-4">
      <div class="mx-auto w-[95%] max-w-[1800px] space-y-4">
        <CommonAppFormErrorSummary :form-errors="[...pageErrors, ...validation.formErrors.value]" />

        <div v-if="!canPublish">
          <UAlert
            color="warning"
            variant="subtle"
            icon="i-lucide-lock"
            title="Publishing is not allowed"
            description="Your role can view configuration versions but cannot create a new one."
          />
        </div>

        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold">New configuration version</h2>
                <p class="text-sm text-muted">
                  Freezes the live tabs, groups and fields as the next active version.
                </p>
              </div>
              <UBadge v-if="active" color="success" variant="subtle">
                {{ t('freight.configVersions.current', { no: active.versionNo }) }}
              </UBadge>
              <UBadge v-else color="warning" variant="subtle">{{ t('freight.configVersions.none') }}</UBadge>
            </div>
          </template>

          <div class="space-y-5">
            <UFormField
              label="Name"
              required
              :error="validation.fieldErrors.value.changeNote"
              data-field-key="changeNote"
            >
              <UInput
                v-model="name"
                :placeholder="t('freight.configVersions.changeNotePlaceholder')"
                class="w-full"
                maxlength="2000"
                @update:model-value="validation.clearFieldError('changeNote')"
                @keyup.enter="save"
              />
            </UFormField>

            <UFormField label="Description">
              <div class="rounded-md border border-default bg-elevated/40 px-3 py-2 text-sm">
                <p>{{ previewTabs.length }} tabs · {{ groupCount }} groups · {{ fieldCount }} fields</p>
                <p class="text-muted">
                  {{ live?.unchanged ? 'The live configuration matches the published version.' : 'These live settings will be captured in the new version.' }}
                </p>
              </div>
            </UFormField>

            <UAlert
              v-if="live && live.tabCount === 0"
              color="warning"
              variant="subtle"
              :title="t('freight.configVersions.emptyTitle')"
              :description="t('freight.configVersions.emptyDescription')"
            />
            <UAlert
              v-else-if="live?.unchanged"
              color="info"
              variant="subtle"
              :description="t('freight.configVersions.unchangedDescription')"
            />
          </div>
        </UCard>

        <ConfigurationSnapshotPreview
          :tabs="previewTabs"
          :trade-directions="live?.tradeDirections"
          description="Read-only preview of what this version will contain."
          empty-text="This configuration contains no tabs yet."
          :loading="config.loading.value"
        />
      </div>
    </div>
  </div>
</template>
