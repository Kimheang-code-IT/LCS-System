<script setup lang="ts">
/**
 * Searchable select for Master Data reference fields. When the field maps to a
 * creatable Master Data page, an "Add new" action is shown in the dropdown; it
 * opens that page and, after saving, the created value is auto-selected back.
 */
import { getFilterSearchInputConfig } from '~/utils/filter/select-ui'
import { referenceCreateTarget } from '~/utils/freight/reference-create'
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
const searchInput = computed(() => getFilterSearchInputConfig(t))

const createTarget = computed(() =>
  props.disabled || props.readonly || !props.referenceKey ? null : referenceCreateTarget(props.referenceKey),
)

function openCreate() {
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
    @update:model-value="onUpdate"
  >
    <template v-if="createTarget" #content-bottom>
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
</template>
