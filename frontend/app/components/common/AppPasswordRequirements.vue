<script setup lang="ts">
/**
 * Live password checklist: one neutral row per approved requirement, marked
 * satisfied as the user types. It renders the same rules the shared validator
 * enforces (`passwordRequirements`), so the list and the submit gate cannot
 * disagree. `aria-live` announces a requirement turning green.
 */
import { PASSWORD_MIN_LENGTH, passwordRequirements } from '~/utils/validation/field-rules'

const props = withDefaults(defineProps<{
  value?: string
}>(), {
  value: '',
})

const { t } = useI18n()
const checks = computed(() => passwordRequirements(String(props.value ?? '')))

const items = computed(() => [
  { key: 'minLength', ok: checks.value.minLength, label: t('validation.passwordMinLength', { min: PASSWORD_MIN_LENGTH }) },
  { key: 'uppercase', ok: checks.value.uppercase, label: t('validation.passwordUppercase') },
  { key: 'lowercase', ok: checks.value.lowercase, label: t('validation.passwordLowercase') },
  { key: 'number', ok: checks.value.number, label: t('validation.passwordNumber') },
  { key: 'special', ok: checks.value.special, label: t('validation.passwordSpecial') },
])
</script>

<template>
  <ul class="space-y-1 text-xs" aria-live="polite">
    <li
      v-for="item in items"
      :key="item.key"
      class="flex items-center gap-1.5"
      :class="item.ok ? 'text-success' : 'text-muted'"
      :data-password-rule="item.key"
      :data-satisfied="item.ok ? 'true' : 'false'"
    >
      <UIcon
        :name="item.ok ? 'i-lucide-check-circle-2' : 'i-lucide-circle'"
        class="size-3.5 shrink-0"
        aria-hidden="true" />
      <span>{{ item.label }}</span>
    </li>
  </ul>
</template>
