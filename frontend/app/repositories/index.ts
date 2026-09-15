import type { RecordAttributeRepository, RecordTypeRepository } from '~/repositories/contracts/configuration'
import type { AppConfigRepository, AppInfoRepository, StorageRepository } from '~/repositories/contracts/settings'
import type {
  AttachmentRepository,
  AuditRepository,
  ComponentRepository,
  FinanceRepository,
  JobRepository,
  OrganizationRepository,
  QuotationRepository,
  ServiceChargeRepository,
  UiSchemaRepository,
} from '~/repositories/contracts/lcs'
import { createHttpRecordAttributeRepository, createHttpRecordTypeRepository } from '~/repositories/http/configuration'
import { createHttpAppConfigRepository, createHttpAppInfoRepository } from '~/repositories/http/settings'
import { createHttpStorageRepository } from '~/repositories/http/settings-storage'
import { createHttpDynamicTabsRepository } from '~/repositories/http/dynamic-tabs'
import type { DynamicTabsRepository } from '~/repositories/contracts/dynamic-tabs'
import {
  createHttpAttachmentRepository,
  createHttpAuditRepository,
  createHttpComponentRepository,
  createHttpFinanceRepository,
  createHttpJobRepository,
  createHttpOrganizationRepository,
  createHttpQuotationRepository,
  createHttpServiceChargeRepository,
  createHttpUiSchemaRepository,
} from '~/repositories/http/lcs'
import { createHttpModuleRepository } from '~/repositories/http/module'
import type { FreightModule } from '~/config/freight-modules'
import type { ModuleRepository } from '~/repositories/contracts/module'

let initialized = false
let recordAttributeRepo: RecordAttributeRepository
let recordTypeRepo: RecordTypeRepository
let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let storageRepo: StorageRepository
let quotationRepo: QuotationRepository
let jobRepo: JobRepository
let componentRepo: ComponentRepository
let chargeRepo: ServiceChargeRepository
let financeRepo: FinanceRepository
let organizationRepo: OrganizationRepository
let auditRepo: AuditRepository
let attachmentRepo: AttachmentRepository
let uiSchemaRepo: UiSchemaRepository
let dynamicTabsRepo: DynamicTabsRepository

function ensureRepositories() {
  if (initialized) return
  initialized = true
  recordAttributeRepo = createHttpRecordAttributeRepository()
  recordTypeRepo = createHttpRecordTypeRepository()
  appInfoRepo = createHttpAppInfoRepository()
  appConfigRepo = createHttpAppConfigRepository()
  storageRepo = createHttpStorageRepository()
  quotationRepo = createHttpQuotationRepository()
  jobRepo = createHttpJobRepository()
  componentRepo = createHttpComponentRepository()
  chargeRepo = createHttpServiceChargeRepository()
  financeRepo = createHttpFinanceRepository()
  organizationRepo = createHttpOrganizationRepository()
  auditRepo = createHttpAuditRepository()
  attachmentRepo = createHttpAttachmentRepository()
  uiSchemaRepo = createHttpUiSchemaRepository()
  dynamicTabsRepo = createHttpDynamicTabsRepository()
}

export function useConfigurationRepositories() {
  ensureRepositories()
  return { attributes: recordAttributeRepo!, recordTypes: recordTypeRepo! }
}

export function useSettingsRepositories() {
  ensureRepositories()
  return { appInfo: appInfoRepo!, appConfig: appConfigRepo!, storage: storageRepo! }
}

export function useLcsRepositories() {
  ensureRepositories()
  return {
    quotations: quotationRepo!,
    jobs: jobRepo!,
    components: componentRepo!,
    charges: chargeRepo!,
    finance: financeRepo!,
    organizations: organizationRepo!,
    audit: auditRepo!,
    attachments: attachmentRepo!,
    uiSchema: uiSchemaRepo!,
    dynamicTabs: dynamicTabsRepo!,
  }
}

export function useModuleRepository(module: FreightModule): ModuleRepository {
  ensureRepositories()
  return createHttpModuleRepository(module)
}
