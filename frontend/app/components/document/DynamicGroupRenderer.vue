<script setup lang="ts">
import type { ComponentTabGroup } from '~/types/component-config'
import { resolveComponentLayout } from '~/utils/freight/component-layout'

const props = withDefaults(defineProps<{
  group: ComponentTabGroup
  rows: Array<Record<string, unknown>>
  references?: Record<string, Record<string, string>>
  editable?: boolean
  saving?: boolean
  /** Cell errors keyed `<groupId>.<rowIndex>.<attributeCode>`. */
  fieldErrors?: Record<string, string>
  onFieldEdit?: (key: string) => void
}>(), {
  references: () => ({}),
  editable: true,
  saving: false,
  fieldErrors: () => ({}),
  onFieldEdit: undefined,
})

const emit = defineEmits<{
  'update:rows': [Array<Record<string, unknown>>]
  'save-group': []
}>()

const layout = computed(() => resolveComponentLayout(props.group))
const editable = computed(() => props.editable && layout.value.editable)

/** A non-collapsible group is always open, whatever its default state says. */
function initialExpanded() {
  return !layout.value.collapsible || layout.value.defaultExpanded
}

const expanded = ref(initialExpanded())

watch(() => [props.group.id, layout.value.collapsible, layout.value.defaultExpanded], () => {
  expanded.value = initialExpanded()
})

const canCollapse = computed(() => layout.value.collapsible && layout.value.showGroupTitle)

function toggle() {
  if (canCollapse.value) expanded.value = !expanded.value
}

const formRow = computed(() => props.rows[0] || {})

function setFormField(code: string, value: unknown) {
  emit('update:rows', [{ ...formRow.value, [code]: value }])
}

const formErrors = computed(() => {
  // Form mode uses row 0, so the parent's canonical paths already line up.
  const scoped: Record<string, string> = {}
  const prefix = `${props.group.id}.0.`
  for (const [key, message] of Object.entries(props.fieldErrors)) {
    if (!key.startsWith(prefix)) continue
    scoped[key.slice(prefix.length)] = message
  }
  return scoped
})
</script>

<template>
  <section class="space-y-3">
    <div v-if="layout.showGroupTitle" class="flex items-center justify-between gap-2">
      <component
        :is="canCollapse ? 'button' : 'h3'"
        :type="canCollapse ? 'button' : undefined"
        class="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-highlighted"
        :aria-expanded="canCollapse ? expanded : undefined"
        @click="toggle"
      >
        <UIcon
          v-if="canCollapse"
          :name="expanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="size-4 shrink-0 text-muted"
        />

        <span class="truncate">{{ group.name }}</span>
      </component>
      <UBadge
        v-if="!editable"
        color="neutral"
        variant="subtle"
        size="sm"
      >
        {{ $t('freight.componentLayout.readOnly') }}
      </UBadge>
    </div>

    <div v-show="expanded">
      <DocumentDynamicFormRenderer
        v-if="layout.displayMode === 'form_only'"
        :group="group"
        :model-value="formRow"
        :references="references"
        :editable="editable"
        :saving="saving"
        :errors="formErrors"
        :field-key-prefix="`${group.id}.0`"
        @update:field="setFormField"
        @submit="emit('save-group')"
      />

      <DocumentDynamicTableRenderer
        v-else-if="layout.displayMode === 'table_only'"
        :group="group"
        :rows="rows"
        :references="references"
        :editable="editable"
        :saving="saving"
        :field-errors="fieldErrors"
        :on-field-edit="onFieldEdit"
        @update:rows="emit('update:rows', $event)"
        @save="emit('save-group')"
      />

      <DocumentDynamicFormTableRenderer
        v-else
        :group="group"
        :rows="rows"
        :references="references"
        :editable="editable"
        :saving="saving"
        :field-errors="fieldErrors"
        :on-field-edit="onFieldEdit"
        @update:rows="emit('update:rows', $event)"
        @save="emit('save-group')"
      />
    </div>
  </section>
</template>
