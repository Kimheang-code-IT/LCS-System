import type { FreightRecord } from '~/types/record'
import type {
  FinanceRepository,
  JobRepository,
  QuotationRepository,
  ServiceChargeRepository,
} from '~/repositories/contracts/lcs'

/**
 * Workflow transitions run through the services that own them.
 *
 * The shared status endpoint (`POST /{collection}/{id}/status`) deliberately
 * refuses these: posting, reversal, issuing a charge, closing a period and the
 * quotation workflow must run their own engine, so the accounting status is
 * never written directly. Each entry here is the frontend half of one
 * "command" transition in the backend policy.
 */
export type StatusCommandRepositories = {
  quotations: Pick<QuotationRepository, 'send' | 'submit' | 'accept' | 'reject' | 'cancel' | 'convert'>
  jobs: Pick<JobRepository, 'finish'>
  charges: Pick<ServiceChargeRepository, 'issue'>
  finance: Pick<FinanceRepository, 'post' | 'reverse' | 'postJournal' | 'closePeriod'>
}

export interface StatusCommandInput {
  id: string
  /** Quotation transitions address the revision, not the header. */
  revisionId: string
  reason?: string
  key: string
  repositories: StatusCommandRepositories
}

export type StatusCommandRunner = (input: StatusCommandInput) => Promise<FreightRecord>

export const STATUS_COMMANDS: Record<string, StatusCommandRunner> = {
  'jobs:finish': ({ id, key, repositories }) => repositories.jobs.finish(id, key),
  'jobCharges:issue': ({ id, key, repositories }) => repositories.charges.issue(id, key),
  'journals:post': ({ id, key, repositories }) => repositories.finance.postJournal(id, key),
  'accountingPeriods:close': ({ id, key, repositories }) => repositories.finance.closePeriod(id, key),
  'debitNotes:post': ({ id, key, repositories }) => repositories.finance.post(id, key),
  'debitNotes:reverse': ({ id, reason, key, repositories }) => repositories.finance.reverse(id, reason || '', key),
  'customerPayments:post': ({ id, key, repositories }) => repositories.finance.post(id, key),
  'customerPayments:reverse': ({ id, reason, key, repositories }) => repositories.finance.reverse(id, reason || '', key),
  'supplierCosts:post': ({ id, key, repositories }) => repositories.finance.post(id, key),
  'supplierCosts:reverse': ({ id, reason, key, repositories }) => repositories.finance.reverse(id, reason || '', key),
  'supplierPayments:post': ({ id, key, repositories }) => repositories.finance.post(id, key),
  'supplierPayments:reverse': ({ id, reason, key, repositories }) => repositories.finance.reverse(id, reason || '', key),
  'quotations:send': ({ revisionId, key, repositories }) => repositories.quotations.send(revisionId, key),
  'quotations:submit': ({ revisionId, key, repositories }) => repositories.quotations.submit(revisionId, key),
  'quotations:accept': ({ revisionId, key, repositories }) => repositories.quotations.accept(revisionId, key),
  'quotations:reject': ({ revisionId, reason, key, repositories }) =>
    repositories.quotations.reject(revisionId, reason || '', key),
  'quotations:cancel': ({ revisionId, reason, key, repositories }) =>
    repositories.quotations.cancel(revisionId, reason || '', key),
  'quotations:convert': ({ revisionId, key, repositories }) => repositories.quotations.convert(revisionId, key),
}

export function hasStatusCommand(collection: string, action: string): boolean {
  return Boolean(STATUS_COMMANDS[`${collection}:${action}`])
}

export function statusCommand(collection: string, action: string): StatusCommandRunner | undefined {
  return STATUS_COMMANDS[`${collection}:${action}`]
}
