<script setup lang="ts">
/**
 * Small inline "Add New" dialog for a Master Data reference select.
 *
 * It exists so a user can create a simple master record (fee type, container
 * type, …) without leaving the document that needs it — the old flow navigated
 * to the Master Data page and back, which destroyed unsaved editing state.
 * Only the fields the backend's creation spec actually requires are shown,
 * duplicates are refused by the backend as field errors (the dialog stays open
 * with every entered value), and on success the new record lands in the store
 * so the select offers it immediately and selects it.
 */
import { normalizeApiError } from '~/utils/validation/api-error'
import { unwrapApiData } from '~/repositories/http/response'
import { canCreateReference, referenceCreateDialog } from '~/utils/freight/reference-create'

const props = defineProps<{
  referenceKey: string
  rowIndex?: number
  disabled?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  created: [value: string]
}>()

const { t } = useI18n()
const auth = useAuthStore()
const api = useApi()
const store = useFreightStore()

const visible = ref(false)
const saving = ref(false)
const values = reactive<Record<string, string>>({ code: '', name: '' })
const fieldErrors = ref<Record<string, string>>({})
const formError = ref('')

const config = computed(() => props.referenceKey ? referenceCreateDialog(props.referenceKey) : null)
const allowed = computed(() =>
  canCreateReference(auth.user?.sourcePermissions, auth.user?.pageAccess, props.referenceKey),
)
const canOpen = computed(() => Boolean(config.value) && allowed.value && !props.disabled && !props.readonly)

function open() {
  if (!canOpen.value) return
  values.code = ''
  values.name = ''
  fieldErrors.value = {}
  formError.value = ''
  visible.value = true
}

function close() {
  // Creation failed or was cancelled: every typed value stays for the next try
  // because only `open` resets them.
  visible.value = false
}

async function create() {
  const target = config.value
  if (!target || saving.value) return
  saving.value = true
  fieldErrors.value = {}
  formError.value = ''
  try {
    const created = unwrapApiData(await api.post<ApiResponse<FreightRecord>>(
      `/api/v1/${target.collection}`,
      { ...values, status: 'Active' },
    )) as Record<string, unknown>
    // The record joins the store's collection, so the select's option list
    // (built from that store) offers it without a reload.
    store.save(target.collection, created as never)
    const value = String(created[target.valueField] ?? created.code ?? created.name ?? '')
    emit('created', value)
    visible.value = false
  }
  catch (error: unknown) {
    // A duplicate code (or any other field refusal) keeps the dialog open with
    // every entered value so nothing has to be retyped.
    const normalized = normalizeApiError(error)
    fieldErrors.value = { ...normalized.fieldErrors }
    formError.value = normalized.message || ''
  }
  finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <UModal v-model:open="visible" :title="t('freight.ui.newEntity', { entity: t(config?.entityKey || '') })">
    <template #content>
      <UCard>
        <p class="mb-4 text-sm text-muted">
          {{ t('freight.ui.referenceCreateHint', { entity: t(config?.entityKey || '') }) }}
        </p>
        <div class="space-y-4">
          <UFormField
            v-for="field in config?.fields || []"
            :key="field.key"
            :label="t(field.labelKey)"
            :error="fieldErrors[field.key]"
            required
          >
            <UInput
              v-model="values[field.key]"
              :maxlength="field.maxLength"
              :disabled="saving"
              class="w-full"
              @update:model-value="fieldErrors[field.key] = ''"
            />
          </UFormField>
          <p v-if="formError" class="text-sm text-error" role="alert">{{ formError }}</p>
        </div>
        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
color="neutral"
variant="ghost"
:disabled="saving"
@click="close">
              {{ t('freight.ui.cancel') }}
            </UButton>
            <UButton color="primary" :loading="saving" @click="create">
              {{ t('freight.ui.save') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>