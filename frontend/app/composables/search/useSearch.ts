import type {
  AiSearchAnswer,
  SearchHit,
  SearchQueryOptions,
} from '~/types/docetra/search'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'

export function useSearch() {
  const api = useApi()

  async function searchKeyword(query: string, options: SearchQueryOptions = {}) {
    const limit = options.limit ?? 12
    try {
      const response = await api.get<{ data: SearchHit[] }>(ApiEndpoints.SEARCH, {
        query: { q: query, mode: 'keyword', limit },
        requestKey: 'search-keyword',
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
        requestKey: 'search-semantic',
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
        requestKey: 'search-ask',
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
  }
}
