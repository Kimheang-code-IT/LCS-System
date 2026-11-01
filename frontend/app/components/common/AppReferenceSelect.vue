<script setup lang="ts">
/**
 * Searchable select for Master Data reference fields. When the field maps to a
 * creatable Master Data page, an "Add new" action is shown in the dropdown:
 * simple masters open an in-form dialog (the quotation keeps its unsaved state
 * and the created record is selected immediately), complex ones navigate to the
 * full Master Data page and return the value via the pick query.
 */
import { getFilterSearchInputConfig } from '~/utils/filter/select-ui'
import { canCreateReference, referenceCreateDialog, referenceCreateTarget } from '~/utils/freight/reference-create'
import { useReferencePick } from '~/composables/freight/useReferencePick'

const props = withDefaults(defineProps<{
  modelValue?: unknown
  items?: Array<{ label: string, value: string }>
  referenceKey?: string
  rowIndex?: number
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  multiple?: boolean
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  clear?: boolean
}>(), {
  modelValue: undefined,
  referenceKey: '',
  rowIndex: undefined,
  placeholder: '',
  items: () => [],
  size: 'md',
  clear: false,
})

const emit = defineEmits<{
  'update:modelValue': [unknown]
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const searchInput = computed(() => getFilterSearchInputConfig(t))

const dialogCreate = useTemplateRef('dialogCreate')

const createAllowed = computed(() =>
  canCreateReference(auth.user?.sourcePermissions, auth.user?.pageAccess, props.referenceKey),
)

const dialogTarget = computed(() =>
  createAllowed.value && !props.disabled && !props.readonly && props.referenceKey
    ? referenceCreateDialog(props.referenceKey)
    : null,
)

const createTarget = computed(() =>
  !props.disabled && !props.readonly && !dialogTarget.value && createAllowed.value && props.referenceKey
    ? referenceCreateTarget(props.referenceKey)
    : null,
)

function openCreate() {
  if (dialogTarget.value) {
    void dialogCreate.value?.open()
    return
  }
  const target = createTarget.value
  if (!target) return
  void router.push({
    path: target.path,
    query: {
      returnTo: route.fullPath,
      pickField: props.referenceKey,
      ...(props.rowIndex !== undefined ? { pickRow: String(props.rowIndex) } : {}),
    },
  })
}

function onCreated(value: string) {
  if (!value) return
  if (props.multiple) {
    const current = Array.isArray(props.modelValue) ? props.modelValue.map(String) : []
    emit('update:modelValue', current.includes(value) ? current : [...current, value])
    return
  }
  emit('update:modelValue', value)
}

const selectModel = computed<string | string[] | undefined>(() => {
  if (props.multiple) return Array.isArray(props.modelValue) ? props.modelValue.map(String) : []
  if (props.modelValue === null || props.modelValue === undefined || props.modelValue === '') return undefined
  return String(props.modelValue)
})

function onUpdate(value: unknown) {
  if (props.multiple) emit('update:modelValue', Array.isArray(value) ? value : [])
  else emit('update:modelValue', value ?? '')
}

const { consume } = useReferencePick()

onMounted(() => {
  if (!props.referenceKey) return
  const picked = consume(props.referenceKey, props.rowIndex)
  if (picked === null) return
  if (props.multiple) {
    const current = Array.isArray(props.modelValue) ? props.modelValue.map(String) : []
    emit('update:modelValue', current.includes(picked) ? current : [...current, picked])
    return
  }
  emit('update:modelValue', picked)
})
</script>

<template>
  <USelectMenu
    :model-value="selectModel"
    :items="items"
    value-key="value"
    :multiple="multiple"
    :placeholder="placeholder"
    :disabled="disabled || readonly"
    :size="size"
    :clear="clear"
    :search-input="searchInput"
    class="w-full"
    @update:model-value="onUpdate"
  >
    <template v-if="createTarget || dialogTarget" #content-bottom>
      <UButton
        block
        color="primary"
        variant="ghost"
        icon="i-lucide-plus"
        :label="t('freight.ui.addNew')"
        @click="openCreate"
      />
    </template>
  </USelectMenu>
  <CommonAppReferenceCreateDialog
    ref="dialogCreate"
    :reference-key="referenceKey"
    :row-index="rowIndex"
    @created="onCreated"
  />
</template>
