<script setup lang="ts">
const model = defineModel<string | undefined>({ default: undefined })

const props = withDefaults(defineProps<{
  label?: string
  labelKey?: string
  help?: string
  helpKey?: string
  accept?: string
  maxSizeMb?: number
  disabled?: boolean
}>(), {
  accept: SAFE_RASTER_IMAGE_ACCEPT,
  maxSizeMb: 2,
  disabled: false,
})

const { t, te } = useI18n()
const toast = useToast()
const inputRef = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const previewSource = computed(() => safeImageSource(model.value))

const labelText = computed(() => {
  if (props.label) return props.label
  if (props.labelKey && te(props.labelKey)) return t(props.labelKey)
  return t('docetra.common.image')
})

const helpText = computed(() => {
  if (props.help) return props.help
  if (props.helpKey && te(props.helpKey)) return t(props.helpKey)
  return t('docetra.common.imageHelp', { size: props.maxSizeMb })
})

function openPicker() {
  if (props.disabled) return
  inputRef.value?.click()
}

function clear() {
  model.value = undefined
}

async function readFile(file: File) {
  if (!SAFE_RASTER_IMAGE_TYPES.includes(file.type as (typeof SAFE_RASTER_IMAGE_TYPES)[number])) {
    toast.add({ title: t('docetra.common.imageInvalidType'), color: 'error' })
    return
  }
  if (!isSafeRasterImage(file, props.maxSizeMb)) {
    toast.add({ title: t('docetra.common.imageTooLarge', { size: props.maxSizeMb }), color: 'error' })
    return
  }
  const reader = new FileReader()
  const dataUrl = await new Promise<string>((resolve, reject) => {
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('read failed'))
    reader.readAsDataURL(file)
  })
  model.value = dataUrl
}

function onInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void readFile(file)
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragOver.value = false
  if (props.disabled) return
  const file = event.dataTransfer?.files?.[0]
  if (file) void readFile(file)
}
</script>

<template>
  <UFormField :label="labelText" :help="helpText">
    <div
      class="relative flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-default bg-elevated/40 p-4 transition"
      :class="[
        dragOver ? 'border-primary bg-primary/5' : '',
        disabled ? 'pointer-events-none opacity-60' : 'hover:border-primary/50',
      ]"
      @click="openPicker"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <template v-if="model">
        <img
v-if="previewSource"
:src="previewSource"
alt=""
class="max-h-24 max-w-full object-contain"
referrerpolicy="no-referrer">
        <div class="flex gap-2">
          <UButton
size="xs"
color="neutral"
variant="soft"
@click.stop="openPicker">
            {{ t('docetra.common.replace') }}
          </UButton>
          <UButton
size="xs"
color="error"
variant="ghost"
@click.stop="clear">
            {{ t('docetra.common.remove') }}
          </UButton>
        </div>
      </template>
      <template v-else>
        <div class="grid size-12 place-items-center rounded-2xl bg-primary/10 ring ring-primary/20">
          <UIcon name="i-lucide-image-up" class="size-6 text-primary" />
        </div>
        <p class="text-sm font-medium text-highlighted">
          {{ t('docetra.common.dropImage') }}
        </p>
      </template>
    </div>
    <input
      ref="inputRef"
      type="file"
      class="hidden"
      :accept="accept"
      :disabled="disabled"
      @change="onInputChange"
    >
  </UFormField>
</template>
