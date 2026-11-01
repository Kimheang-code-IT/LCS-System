<script setup lang="ts">
/**
 * Quick Entry: one reusable "New <Master Data>" modal.
 *
 * The form is not hand-built per master. It renders the module's own declared
 * fields (`freight-modules.ts`) with the shared field grid, validates them with
 * the shared rules, and posts to the same `/api/v1/<collection>` endpoint the
 * full Master Data page uses. A new master declaration therefore gets Quick
 * Entry everywhere without touching this file.
 *
 * The parent form is never touched: the modal is an overlay, cancelling leaves
 * every entered value of the document alone, and a refused save keeps the modal
 * open with its own values intact.
 */
import { emptyFreightRecord, useFreightLabel } from '~/composables/freight/useFreight'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { unwrapApiData } from '~/repositories/http/response'
import {
  canCreateReference,
  referenceCreateModule,
  referenceCreateValueField,
} from '~/utils/freight/reference-create'
import { validateDraftFields } from '~/utils/validation/record-validation'
import type { FreightField } from '~/config/freight-modules'

const props = defineProps<{
  referenceKey: string
  disabled?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  created: [value: string]
}>()

const { t } = useI18n()
const { fieldLabel, moduleSingular } = useFreightLabel()
const auth = useAuthStore()
const api = useApi()
const store = useFreightStore()

const visible = ref(false)
const model = ref<Record<string, unknown>>({})

const createModule = computed(() =>
  props.referenceKey ? referenceCreateModule(props.referenceKey) : null,
)
/** Computed fields are rendered disabled by the grid, so they need no width. */
const fields = computed<FreightField[]>(() =>
  (createModule.value?.fields || []).filter(field => !field.computed),
)
const allowed = computed(() =>
  canCreateReference(auth.user?.sourcePermissions, auth.user?.pageAccess, props.referenceKey),
)
const canOpen = computed(() =>
  Boolean(createModule.value) && allowed.value && !props.disabled && !props.readonly,
)
const title = computed(() => {
  const target = createModule.value
  return target
    ? t('freight.ui.newEntity', { entity: moduleSingular(target) })
    : ''
})

const validation = useFormValidation({
  t,
  label: fieldLabelOf,
  order: () => fields.value.map(field => field.key),
})

function fieldLabelOf(key: string) {
  const field = fields.value.find(item => item.key === key)
  return fieldLabel(field || { key, label: key, labelKm: '' })
}

function open() {
  const target = createModule.value
  if (!canOpen.value || !target) return
  // Defaults come from the same helper the full page uses (status, dates,
  // numbers, multiselects), so both entry points start identical.
  model.value = emptyFreightRecord(target)
  validation.reset()
  visible.value = true
}

function close() {
  // Cancel keeps nothing to restore: the parent form was never unmounted.
  visible.value = false
}

function onUpdate(key: string, value: unknown) {
  model.value = { ...model.value, [key]: value }
  validation.clearFieldError(key)
}

async function create() {
  const target = createModule.value
  if (!target || validation.submitting.value) return
  const failures = validateDraftFields(model.value, fields.value, fieldLabelOf)
  if (failures.length) {
    validation.applyFailures(failures)
    return
  }
  validation.reset()
  validation.submitting.value = true
  try {
    // Computed fields are derived by the backend on create; sending them would
    // pin values the user never typed.
    const payload = referenceCreatePayload(target, model.value)
    const created = unwrapApiData(await api.post<ApiResponse<FreightRecord>>(
      `/api/v1/${target.collection}`,
      payload,
    )) as Record<string, unknown>
    // The record joins the store's collection, so the select's option list
    // (built from that store) offers it without a reload.
    store.save(target.collection, created as never)
    const value = String(
      created[referenceCreateValueField(props.referenceKey)]
      ?? created.code
      ?? created.name
      ?? created.id
      ?? '',
    )
    emit('created', value)
    visible.value = false
  }
  catch (error: unknown) {
    // A duplicate code (or any other backend refusal) keeps the modal open with
    // every entered value, and the field errors land on the inputs.
    validation.applyServerError(error)
  }
  finally {
    validation.submitting.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <!--
    Nuxt UI's own header/body/footer slots keep the title and Close pinned while
    only the body scrolls. The width is set once here for every Quick Entry form.
  -->
  <UModal
    v-model:open="visible"
    :title="title"
    :ui="{ content: 'w-[calc(100vw-2rem)] max-w-[1005px] sm:max-w-[1005px]' }"
  >
    <template #body>
      <DocumentAppFieldGrid
        :fields="fields"
        :model="model"
        :field-errors="validation.fieldErrors.value"
        :disabled="validation.submitting.value"
        key-prefix="quick-entry-"
        @update="onUpdate"
      />
      <p
        v-for="message in validation.formErrors.value"
        :key="message"
        class="mt-4 text-sm text-error"
        role="alert"
      >
        {{ message }}
      </p>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :disabled="validation.submitting.value"
          @click="close">
          {{ t('freight.ui.cancel') }}
        </UButton>
        <UButton color="primary" :loading="validation.submitting.value" @click="create">
          {{ t('freight.ui.saveAndSelect') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
