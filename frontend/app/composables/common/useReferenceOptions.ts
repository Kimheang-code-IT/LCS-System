import type { ApiResponse, FieldOption } from '~/types/docetra/common'

const OPTIONS_CACHE_TTL_MS = 60_000
const optionsCache = new Map<string, {
  at: number
  data: FieldOption[]
  inflight?: Promise<FieldOption[]>
}>()

function optionsValueField(endpoint: string): 'id' | 'name' {
  try {
    const query = endpoint.includes('?') ? endpoint.slice(endpoint.indexOf('?') + 1) : ''
    const params = new URLSearchParams(query)
    return params.get('valueField') === 'name' ? 'name' : 'id'
  }
  catch {
    return 'id'
  }
}

function endpointPath(endpoint: string) {
  return endpoint.split('?')[0] || endpoint
}

function endpointParams(endpoint: string) {
  const query = endpoint.includes('?') ? endpoint.slice(endpoint.indexOf('?') + 1) : ''
  return new URLSearchParams(query)
}

export function useReferenceOptions() {
  const api = useApi()

  async function loadReferenceOptionsUncached(endpoint: string, search = ''): Promise<FieldOption[]> {
    const path = endpointPath(endpoint)
    const params = endpointParams(endpoint)
    const valueField = optionsValueField(endpoint)

    const response = await api.get<ApiResponse<FieldOption[]> | FieldOption[]>(path, {
      query: {
        q: search || undefined,
        limit: 50,
        status: 'active',
        valueField,
        hierarchy: params.get('hierarchy') || undefined,
        excludeId: params.get('excludeId') || undefined,
      },
      suppressErrorToast: true,
      requestKey: `field-options:${endpoint}`,
      cancelPrevious: true,
    })
    return Array.isArray(response) ? response : response.data
  }

  async function loadReferenceOptions(endpoint: string, search = '') {
    const cacheKey = `${endpoint}::${search}`
    if (!search) {
      const cached = optionsCache.get(cacheKey)
      if (cached?.inflight) return cached.inflight
      if (cached && Date.now() - cached.at < OPTIONS_CACHE_TTL_MS) return cached.data
    }

    const inflight = loadReferenceOptionsUncached(endpoint, search)
    if (!search) {
      optionsCache.set(cacheKey, { at: 0, data: [], inflight })
    }

    try {
      const data = await inflight
      if (!search) {
        optionsCache.set(cacheKey, { at: Date.now(), data })
      }
      return data
    }
    catch (error) {
      if (!search) optionsCache.delete(cacheKey)
      throw error
    }
  }

  return {
    loadReferenceOptions,
  }
}
