<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue?: string
  label?: string
  labelKey?: string
  placeholder?: string
  help?: string
  helpKey?: string
  disabled?: boolean
  autocomplete?: string
}>(), {
  modelValue: '',
  autocomplete: 'new-password',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [string]
}>()

const { t, te } = useI18n()
const revealed = ref(false)

const labelText = computed(() => {
  if (props.label) return props.label
  if (props.labelKey && te(props.labelKey)) return t(props.labelKey)
  return ''
})

const helpText = computed(() => {
  if (props.help) return props.help
  if (props.helpKey && te(props.helpKey)) return t(props.helpKey)
  return ''
})

const value = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
})
</script>

<template>
  <UFormField :label="labelText" :help="helpText || undefined">
    <UInput
      v-model="value"
      :type="revealed ? 'text' : 'password'"
      :placeholder="placeholder"
      :disabled="disabled"
      :autocomplete="autocomplete"
      size="md"
      class="w-full"
      :ui="{ trailing: 'pe-1' }"
    >
      <template #trailing>
        <UButton
          :icon="revealed ? 'i-lucide-eye-off' : 'i-lucide-eye'"
          color="neutral"
          variant="link"
          size="sm"
          :aria-label="revealed ? t('docetra.common.hideSecret') : t('docetra.common.showSecret')"
          :disabled="disabled"
          @click="revealed = !revealed"
        />
      </template>
    </UInput>
  </UFormField>
</template>
