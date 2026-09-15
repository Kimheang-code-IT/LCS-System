import type { RecordAttributeRepository, RecordTypeRepository } from '~/repositories/contracts/configuration'
import type { ActivityEvent, ApiResponse, EntityComment } from '~/types/docetra/common'
import type { RecordAttribute, RecordType, ResolvedRecordTypeSchema } from '~/types/docetra/configuration'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { unwrapApiData } from './response'

export function createHttpRecordAttributeRepository(): RecordAttributeRepository {
  const api = useApi()
  const resource = (id: string) => `${ApiEndpoints.RECORD_ATTRIBUTES}/${encodeURIComponent(id)}`

  return {
    list: query => api.get<ApiResponse<RecordAttribute[]>>(ApiEndpoints.RECORD_ATTRIBUTES, { query }),
    getById: async id => unwrapApiData(await api.get<RecordAttribute | ApiResponse<RecordAttribute>>(resource(id))),
    create: async input => unwrapApiData(await api.post<RecordAttribute | ApiResponse<RecordAttribute>>(ApiEndpoints.RECORD_ATTRIBUTES, input)),
    update: async (id, input) => unwrapApiData(await api.patch<RecordAttribute | ApiResponse<RecordAttribute>>(resource(id), input)),
    duplicate: async id => unwrapApiData(await api.post<RecordAttribute | ApiResponse<RecordAttribute>>(`${resource(id)}/duplicate`, {})),
    setActive: async (id, active) => unwrapApiData(await api.patch<RecordAttribute | ApiResponse<RecordAttribute>>(`${resource(id)}/status`, { active })),
    remove: async id => { await api.delete(resource(id)) },
    removeMany: async ids => { await api.post(`${ApiEndpoints.RECORD_ATTRIBUTES}/bulk-delete`, { ids }) },
    listComments: (id, query) => api.get<ApiResponse<EntityComment[]>>(`${resource(id)}/comments`, { query }),
    addComment: (id, body) => api.post<ApiResponse<EntityComment>>(`${resource(id)}/comments`, { body }),
    updateComment: (id, commentId, body) => api.patch<ApiResponse<EntityComment>>(`${resource(id)}/comments/${encodeURIComponent(commentId)}`, { body }),
    deleteComment: (id, commentId) => api.delete<ApiResponse<{ id: string }>>(`${resource(id)}/comments/${encodeURIComponent(commentId)}`),
    listActivity: (id, query) => api.get<ApiResponse<ActivityEvent[]>>(`${resource(id)}/activity`, { query }),
  }
}

export function createHttpRecordTypeRepository(): RecordTypeRepository {
  const api = useApi()
  const resource = (id: string) => `${ApiEndpoints.RECORD_TYPES}/${encodeURIComponent(id)}`

  return {
    list: query => api.get<ApiResponse<RecordType[]>>(ApiEndpoints.RECORD_TYPES, { query }),
    getById: async id => unwrapApiData(await api.get<RecordType | ApiResponse<RecordType>>(resource(id))),
    getResolvedSchema: async lookup => unwrapApiData(await api.get<ResolvedRecordTypeSchema | ApiResponse<ResolvedRecordTypeSchema>>(
      lookup.id
        ? `${resource(lookup.id)}/schema`
        : `${ApiEndpoints.RECORD_TYPES}/by-code/${encodeURIComponent(lookup.code || '')}/schema`,
      { requestKey: `record-type-schema:${lookup.id || lookup.code}`, cancelPrevious: true },
    )),
    create: async input => unwrapApiData(await api.post<RecordType | ApiResponse<RecordType>>(ApiEndpoints.RECORD_TYPES, input)),
    update: async (id, input) => unwrapApiData(await api.patch<RecordType | ApiResponse<RecordType>>(resource(id), input)),
    duplicate: async id => unwrapApiData(await api.post<RecordType | ApiResponse<RecordType>>(`${resource(id)}/duplicate`, {})),
    setActive: async (id, active) => unwrapApiData(await api.patch<RecordType | ApiResponse<RecordType>>(`${resource(id)}/status`, { active })),
    remove: async id => { await api.delete(resource(id)) },
    removeMany: async ids => { await api.post(`${ApiEndpoints.RECORD_TYPES}/bulk-delete`, { ids }) },
    listComments: (id, query) => api.get<ApiResponse<EntityComment[]>>(`${resource(id)}/comments`, { query }),
    addComment: (id, body) => api.post<ApiResponse<EntityComment>>(`${resource(id)}/comments`, { body }),
    updateComment: (id, commentId, body) => api.patch<ApiResponse<EntityComment>>(`${resource(id)}/comments/${encodeURIComponent(commentId)}`, { body }),
    deleteComment: (id, commentId) => api.delete<ApiResponse<{ id: string }>>(`${resource(id)}/comments/${encodeURIComponent(commentId)}`),
    listActivity: (id, query) => api.get<ApiResponse<ActivityEvent[]>>(`${resource(id)}/activity`, { query }),
  }
}
