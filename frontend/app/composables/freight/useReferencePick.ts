import type { LocationQuery } from 'vue-router'

/**
 * Reads the `pickField` / `pickRow` / `pickedValue` query params set by the
 * "Add new" master-data flow and returns the created value so the originating
 * select can auto-select it, then clears the params.
 */
export function useReferencePick() {
  const route = useRoute()
  const router = useRouter()

  function consume(key: string, rowIndex?: number): string | null {
    const query = route.query
    if (String(query.pickField || '') !== key) return null
    if (!('pickedValue' in query)) return null
    if (rowIndex !== undefined && String(query.pickRow ?? '') !== String(rowIndex)) return null
    const picked = query.pickedValue
    const value = Array.isArray(picked) ? String(picked[0] ?? '') : String(picked ?? '')

    const next: LocationQuery = { ...query }
    delete next.pickField
    delete next.pickedValue
    delete next.pickRow
    void router.replace({ query: next })

    return value
  }

  return { consume }
}
