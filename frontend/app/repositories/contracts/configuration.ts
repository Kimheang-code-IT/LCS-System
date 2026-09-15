import type { ActivityEvent, ApiResponse, EntityComment, ListQuery } from '~/types/docetra/common'
import type {
  CreateRecordAttributeInput,
  CreateRecordTypeInput,
  RecordAttribute,
  RecordAttributeQuery,
  RecordType,
  ResolvedRecordTypeSchema,
  RecordTypeQuery,
  UpdateRecordAttributeInput,
  UpdateRecordTypeInput,
} from '~/types/docetra/configuration'

export interface ConfigurationDiscussionRepository {
  listComments: (id: string, query?: ListQuery) => Promise<ApiResponse<EntityComment[]>>
  addComment: (id: string, body: string, author?: EntityComment['author']) => Promise<ApiResponse<EntityComment>>
  updateComment: (id: string, commentId: string, body: string) => Promise<ApiResponse<EntityComment>>
  deleteComment: (id: string, commentId: string) => Promise<ApiResponse<{ id: string }>>
  listActivity: (id: string, query?: ListQuery) => Promise<ApiResponse<ActivityEvent[]>>
}

export interface RecordAttributeRepository extends ConfigurationDiscussionRepository {
  list: (query?: RecordAttributeQuery) => Promise<ApiResponse<RecordAttribute[]>>
  getById: (id: string) => Promise<RecordAttribute>
  create: (input: CreateRecordAttributeInput) => Promise<RecordAttribute>
  update: (id: string, input: UpdateRecordAttributeInput) => Promise<RecordAttribute>
  duplicate: (id: string) => Promise<RecordAttribute>
  setActive: (id: string, active: boolean) => Promise<RecordAttribute>
  remove: (id: string) => Promise<void>
  removeMany: (ids: string[]) => Promise<void>
}

export interface RecordTypeRepository extends ConfigurationDiscussionRepository {
  list: (query?: RecordTypeQuery) => Promise<ApiResponse<RecordType[]>>
  getById: (id: string) => Promise<RecordType>
  getResolvedSchema: (lookup: { id?: string, code?: string }) => Promise<ResolvedRecordTypeSchema>
  create: (input: CreateRecordTypeInput) => Promise<RecordType>
  update: (id: string, input: UpdateRecordTypeInput) => Promise<RecordType>
  duplicate: (id: string) => Promise<RecordType>
  setActive: (id: string, active: boolean) => Promise<RecordType>
  remove: (id: string) => Promise<void>
  removeMany: (ids: string[]) => Promise<void>
}
