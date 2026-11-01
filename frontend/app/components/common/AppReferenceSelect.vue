<script setup lang="ts">
/**
 * Searchable select for Master Data reference fields. When the field maps to a
 * creatable Master Data module, an "Add new" action is shown in the dropdown: it
 * opens the shared Quick Entry modal, so the parent form keeps every typed value
 * and the created record is selected immediately.
 */
import { getFilterSearchInputConfig } from '~/utils/filter/select-ui'
import { canCreateReference, referenceCreateModule } from '~/utils/freight/reference-create'
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
const auth = useAuthStore()
const searchInput = computed(() => getFilterSearchInputConfig(t))

const dialogCreate = useTemplateRef('dialogCreate')
const menuOpen = ref(false)

const createAllowed = computed(() =>
  canCreateReference(auth.user?.sourcePermissions, auth.user?.pageAccess, props.referenceKey),
)

const createModule = computed(() =>
  createAllowed.value && !props.disabled && !props.readonly && props.referenceKey
    ? referenceCreateModule(props.referenceKey)
    : null,
)

function openCreate() {
  // Close the dropdown first so its popover cannot sit on top of the modal.
  menuOpen.value = false
  if (!createModule.value) return
  void dialogCreate.value?.open()
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
    v-model:open="menuOpen"
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
    <template v-if="createModule" #content-bottom>
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
    @created="onCreated"
  />
</template>
