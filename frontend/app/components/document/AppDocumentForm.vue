<script setup lang="ts">
import type { DocumentTabSchema } from '~/types/docetra/common'
import { freightDocumentRecordKey } from '~/utils/freight/document-tabs'

const props = withDefaults(defineProps<{
  tabs: DocumentTabSchema[]
  activeTab: string
  fieldValue: (key: string) => unknown
  setFieldValue: (key: string, value: unknown) => void
  readOnly?: boolean
  /** Force wider shell even without dense field types. */
  wide?: boolean
}>(), {
  readOnly: false,
  wide: false,
})

const { t, te } = useI18n()

provide(freightDocumentRecordKey, {
  get: (key: string) => props.fieldValue(key),
})

function sectionHeading(section: DocumentTabSchema['sections'][0]) {
  if (section.titleKey && te(section.titleKey)) return t(section.titleKey)
  return section.title || ''
}

function sectionDescription(section: DocumentTabSchema['sections'][0]) {
  if (section.descriptionKey && te(section.descriptionKey)) return t(section.descriptionKey)
  return section.description || ''
}

const wideForm = computed(() =>
  props.wide
  || props.tabs.some(tab =>
    tab.sections.some(section =>
      section.fields.some(field =>
        field.type === 'telegram-destinations'
        || field.type === 'notification-rules'
        || field.type === 'line-table'
        || field.type === 'related-records'
        || field.type === 'dynamic-table',
      ),
    ),
  ),
)

function isFullWidthField(field: DocumentTabSchema['sections'][0]['fields'][0]) {
  return field.colSpan === 2
    || field.type === 'textarea'
    || field.type === 'image'
    || field.type === 'permission-matrix'
    || field.type === 'telegram-destinations'
    || field.type === 'notification-rules'
    || field.type === 'connection-status'
    || field.type === 'alert'
    || field.type === 'assigned-attributes'
    || field.type === 'workflow-builder'
    || field.type === 'numbering-preview'
    || field.type === 'validation-builder'
    || field.type === 'options-builder'
    || field.type === 'visibility-builder'
    || field.type === 'line-table'
    || field.type === 'related-records'
}
</script>

<template>
  <div class="min-w-0 w-full flex-1 overflow-x-hidden">
    <DocumentAppDocumentContentShell :wide="wideForm">
      <template v-for="tab in tabs" :key="tab.id">
        <div v-show="activeTab === tab.id || tabs.length === 1" class="space-y-8 py-6">
          <section
            v-for="(section, sectionIndex) in tab.sections"
            :key="section.id"
            class="space-y-4"
            :class="sectionIndex > 0 ? 'border-t border-default pt-6' : ''"
          >
            <div v-if="sectionHeading(section) || sectionDescription(section)">
              <h3 v-if="sectionHeading(section)" class="text-sm font-medium text-highlighted">
                {{ sectionHeading(section) }}
              </h3>
              <p v-if="sectionDescription(section)" class="mt-1 text-xs text-muted">
                {{ sectionDescription(section) }}
              </p>
            </div>

            <div class="grid min-w-0 grid-cols-1 gap-x-5 gap-y-5 sm:grid-cols-2">
              <div
                v-for="field in section.fields"
                :key="field.key"
                class="min-w-0 max-w-full"
                :class="isFullWidthField(field) ? 'sm:col-span-2' : ''"
              >
                <DocumentAppDynamicFieldRenderer
                  :field="field"
                  :model-value="fieldValue(field.key)"
                  :disabled="readOnly || Boolean(field.readOnly)"
                  @update:model-value="(v) => setFieldValue(field.key, v)"
                />
              </div>
            </div>
          </section>
        </div>
      </template>
    </DocumentAppDocumentContentShell>
  </div>
</template>
