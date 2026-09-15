import type {
  DynamicColumnInput,
  DynamicTab,
  DynamicTabColumn,
  DynamicTabInput,
  DynamicTabRow,
  DynamicTabsBootstrap,
} from '~/types/freight/dynamic-tabs'

export interface DynamicRowInput {
  id?: string
  values: Record<string, unknown>
}

export interface DynamicTabsRepository {
  /** Bulk load: active tabs + columns + this service order's rows + reference options. */
  bootstrap: (serviceOrderId: string) => Promise<DynamicTabsBootstrap>
  listTabs: (includeArchived?: boolean) => Promise<DynamicTab[]>
  createTab: (input: DynamicTabInput) => Promise<DynamicTab>
  updateTab: (id: string, input: DynamicTabInput) => Promise<DynamicTab>
  deleteTab: (id: string) => Promise<{ archived: boolean, id: string }>
  listColumns: (tabId: string, includeArchived?: boolean) => Promise<DynamicTabColumn[]>
  createColumn: (tabId: string, input: DynamicColumnInput) => Promise<DynamicTabColumn>
  updateColumn: (id: string, input: DynamicColumnInput) => Promise<DynamicTabColumn>
  deleteColumn: (id: string) => Promise<{ archived: boolean, id: string }>
  reorderColumns: (tabId: string, orderedIds: string[]) => Promise<DynamicTabColumn[]>
  saveRows: (serviceOrderId: string, tabId: string, rows: DynamicRowInput[]) => Promise<DynamicTabRow[]>
}
