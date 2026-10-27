import { describe, expect, it, vi } from 'vitest'
import type { RecordStatusPolicy } from '../app/types/status'
import { freightModules, getFreightModule } from '../app/config/freight-modules'
import { isNetworkFailure } from '../app/utils/api/errors'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import {
  normalizeRecordStatus,
  statusActionMeta,
  statusTransitionsFor,
  statusValueOf,
  supportsStatusPolicy,
} from '../app/utils/freight/status-actions'
import { STATUS_COMMANDS, hasStatusCommand, statusCommand } from '../app/utils/freight/status-commands'

const policy: RecordStatusPolicy = {
  collection: 'placeRoles',
  statuses: ['ACTIVE', 'INACTIVE'],
  transitions: {
    ACTIVE: [{ to: 'INACTIVE', action: 'deactivate', kind: 'status', confirm: false, reason: false }],
    INACTIVE: [{ to: 'ACTIVE', action: 'activate', kind: 'status', confirm: false, reason: false }],
  },
}

describe('status transitions', () => {
  it('matches the record status case-insensitively', () => {
    expect(normalizeRecordStatus('  Active ')).toBe('ACTIVE')
    expect(statusTransitionsFor(policy, 'Active')).toEqual(policy.transitions.ACTIVE)
    expect(statusTransitionsFor(policy, 'INACTIVE')).toEqual(policy.transitions.INACTIVE)
  })

  it('offers nothing without a policy or without a matching status', () => {
    expect(statusTransitionsFor(null, 'ACTIVE')).toEqual([])
    expect(statusTransitionsFor(policy, 'FINISHED')).toEqual([])
    expect(statusTransitionsFor(policy, '')).toEqual([])
  })

  it('reads the revision status on a quotation row', () => {
    // The header status mirrors the revision, but the transition belongs to it.
    expect(statusValueOf({ status: 'Accepted', revisionStatus: 'SENT' })).toBe('SENT')
    expect(statusValueOf({ status: 'ACTIVE' })).toBe('ACTIVE')
    expect(statusValueOf({ workflowStatus: 'OPEN' })).toBe('OPEN')
  })

  it('labels each verb and falls back for an unknown one', () => {
    expect(statusActionMeta('deactivate')).toMatchObject({ labelKey: 'freight.statusActions.deactivate' })
    expect(statusActionMeta('somethingNew')).toMatchObject({ icon: 'i-lucide-circle-dot' })
  })
})

describe('status policy support', () => {
  it('never asks for a policy on a historical or derived page', () => {
    // Regression: the Audit Logs page requested /auditLogs/status-policy, which
    // answers 404 by design, and the shared status manager turned that expected
    // answer into a user-visible error.
    for (const path of [
      '/administration/audit-logs',
      '/administration/archive',
      '/reports',
      '/finance/accounts-receivable',
      '/finance/accounts-payable',
      '/finance/job-profitability',
    ]) {
      const module = getFreightModule(path)
      expect(module, path).toBeTruthy()
      expect(supportsStatusPolicy(module!), path).toBe(false)
    }
  })

  it('keeps the policy request for modules with a lifecycle', () => {
    for (const path of [
      '/operations/jobs',
      '/sales/quotations',
      '/administration/users',
      '/administration/roles',
      '/sales/companies',
      '/finance/customer-payments',
    ]) {
      expect(supportsStatusPolicy(getFreightModule(path)!), path).toBe(true)
    }
  })

  it('never treats an HTTP error answer as a connection failure', () => {
    // ofetch calls both a 404 and a dropped connection a FetchError.
    expect(isNetworkFailure({ name: 'FetchError', status: 404, statusCode: 404 })).toBe(false)
    expect(isNetworkFailure({ name: 'FetchError', status: 500 })).toBe(false)
    expect(isNetworkFailure({ name: 'FetchError' })).toBe(true)
    expect(isNetworkFailure({ name: 'AbortError' })).toBe(false)
    expect(isNetworkFailure(undefined)).toBe(false)
  })
})

describe('status commands', () => {
  it('keeps one runner per workflow transition key', () => {
    for (const key of Object.keys(STATUS_COMMANDS)) {
      const [collection, action] = key.split(':')
      expect(hasStatusCommand(collection!, action!), key).toBe(true)
      expect(statusCommand(collection!, action!), key).toBeTruthy()
    }
    expect(hasStatusCommand('placeRoles', 'deactivate')).toBe(false)
  })

  it('dispatches each workflow action to the endpoint that owns it', async () => {
    const calls: string[] = []
    const record = { id: '1' }
    const repositories = {
      quotations: {
        send: vi.fn(async () => { calls.push('quotations.send'); return record }),
        accept: vi.fn(async () => { calls.push('quotations.accept'); return record }),
        reject: vi.fn(async () => { calls.push('quotations.reject'); return record }),
        cancel: vi.fn(async () => { calls.push('quotations.cancel'); return record }),
        convert: vi.fn(async () => { calls.push('quotations.convert'); return record }),
      },
      jobs: { finish: vi.fn(async () => { calls.push('jobs.finish'); return record }) },
      charges: { issue: vi.fn(async () => { calls.push('charges.issue'); return record }) },
      finance: {
        post: vi.fn(async () => { calls.push('finance.post'); return record }),
        reverse: vi.fn(async () => { calls.push('finance.reverse'); return record }),
        postJournal: vi.fn(async () => { calls.push('finance.postJournal'); return record }),
        closePeriod: vi.fn(async () => { calls.push('finance.closePeriod'); return record }),
      },
    }

    const run = (collection: string, action: string) =>
      statusCommand(collection, action)!({
        id: '5', revisionId: '9', reason: 'wrong rate', key: 'idem', repositories,
      })

    await run('jobs', 'finish')
    await run('jobCharges', 'issue')
    await run('journals', 'post')
    await run('accountingPeriods', 'close')
    await run('debitNotes', 'post')
    await run('debitNotes', 'reverse')
    await run('customerPayments', 'post')
    await run('quotations', 'send')
    await run('quotations', 'accept')
    await run('quotations', 'reject')
    await run('quotations', 'cancel')
    await run('quotations', 'convert')

    // A quotation transition addresses the revision; the others the record id.
    expect(repositories.quotations.send).toHaveBeenCalledWith('9', 'idem')
    expect(repositories.quotations.reject).toHaveBeenCalledWith('9', 'wrong rate', 'idem')
    expect(repositories.quotations.cancel).toHaveBeenCalledWith('9', 'wrong rate', 'idem')
    expect(repositories.finance.reverse).toHaveBeenCalledWith('5', 'wrong rate', 'idem')
    expect(calls).toEqual([
      'jobs.finish',
      'charges.issue',
      'finance.postJournal',
      'finance.closePeriod',
      'finance.post',
      'finance.reverse',
      'finance.post',
      'quotations.send',
      'quotations.accept',
      'quotations.reject',
      'quotations.cancel',
      'quotations.convert',
    ])
  })
})

describe('status is never an editable form field', () => {
  it('keeps every compiled module form free of a status field', () => {
    const withStatusField = freightModules.filter(module => module.fields.some(field => field.key === 'status'))
    expect(withStatusField.length, 'the module configs do declare status fields').toBeGreaterThan(10)

    for (const module of freightModules) {
      const tabs = moduleDocumentTabs(module)
      const keys = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields.map(field => field.key)))
      expect(keys, `${module.path} must not expose a status field`).not.toContain('status')
    }
  })
})
