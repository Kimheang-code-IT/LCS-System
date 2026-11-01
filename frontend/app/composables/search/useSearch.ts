import type {
  AiSearchAnswer,
  SearchHit,
  SearchQueryOptions,
} from '~/types/search'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { createClientId } from '~/utils/client-id'

export function useSearch() {
  const api = useApi()
  // A palette must not cancel requests owned by another mounted consumer.
  const requestKey = createClientId('search')

  function cancelSearch() {
    api.cancelRequest(`${requestKey}:keyword`)
    api.cancelRequest(`${requestKey}:semantic`)
  }

  function cancelAsk() {
    api.cancelRequest(`${requestKey}:ask`)
  }

  async function searchKeyword(query: string, options: SearchQueryOptions = {}) {
    const limit = options.limit ?? 12
    try {
      const response = await api.get<{ data: SearchHit[] }>(ApiEndpoints.SEARCH, {
        query: { q: query, mode: 'keyword', limit },
        requestKey: `${requestKey}:keyword`,
        cancelPrevious: true,
        suppressErrorToast: true,
      })
      return (response as { data: SearchHit[] }).data || []
    }
    catch {
      return []
    }
  }

  async function searchSemantic(query: string, options: SearchQueryOptions = {}) {
    const limit = options.limit ?? 12
    try {
      const response = await api.get<{ data: SearchHit[] }>(ApiEndpoints.SEARCH, {
        query: { q: query, mode: 'semantic', limit },
        requestKey: `${requestKey}:semantic`,
        cancelPrevious: true,
        suppressErrorToast: true,
      })
      return (response as { data: SearchHit[] }).data || []
    }
    catch {
      return []
    }
  }

  async function askAi(query: string, hits: SearchHit[]): Promise<AiSearchAnswer> {
    try {
      const response = await api.post<{ data: AiSearchAnswer }>(ApiEndpoints.SEARCH_ASK, {
        q: query,
        hitIds: hits.map(h => h.id),
      }, {
        requestKey: `${requestKey}:ask`,
        cancelPrevious: true,
        suppressErrorToast: true,
      })
      return (response as { data: AiSearchAnswer }).data
    }
    catch {
      return { answer: '', citations: [] }
    }
  }

  return {
    searchKeyword,
    searchSemantic,
    askAi,
    cancelSearch,
    cancelAsk,
  }
}
