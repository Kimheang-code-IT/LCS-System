import { useMaintenanceRepository } from '~/repositories/http/maintenance'
import { useFormValidation } from '~/composables/common/useFormValidation'
import type { MaintenanceSettings } from '~/types/maintenance'
import { compactMaintenanceChange } from '~/utils/settings/maintenance'
import { validateFieldValue } from '~/utils/validation/field-rules'

/** One editor shared by the Maintenance and Backup tabs; rendering owns no API calls. */
export function useMaintenanceSettings() {
  const repo = useMaintenanceRepository()
  const { $i18n } = useNuxtApp()
  const stored = ref<MaintenanceSettings | null>(null)
  const draft = ref({ enabled: false, reason: '' })
  const validation = useFormValidation({ t: (key, params) => $i18n.t(key, params ?? {}), order: () => ['enabled', 'reason'] })
  const changed = computed(() => stored.value !== null && (draft.value.enabled !== stored.value.enabled || draft.value.reason !== stored.value.reason))

  async function load() {
    stored.value = await repo.get()
    draft.value = { enabled: stored.value.enabled, reason: stored.value.reason }
    validation.reset()
  }
  function validate() {
    validation.reset()
    if (!stored.value) {
      validation.addFormError($i18n.t('lcs.common.loadFailed'))
      return false
    }
    const issue = changed.value ? validateFieldValue(draft.value.reason, { required: true, maxLength: 500 }) : null
    if (issue) {
      validation.applyFailures([{ key: 'reason', label: $i18n.t('maintenance.reason'), ...issue }])
      void validation.focusFirstInvalid()
      return false
    }
    return true
  }
  async function save() {
    if (!changed.value) return true
    if (!stored.value || !validate()) return false
    try {
      const saved = await repo.save(compactMaintenanceChange(stored.value, draft.value))
      stored.value = saved
      draft.value = { enabled: saved.enabled, reason: saved.reason }
      return true
    }
    catch (error) {
      validation.applyServerError(error)
      await validation.focusFirstInvalid()
      return false
    }
  }
  return { draft, changed, load, validate, save, validation }
}
