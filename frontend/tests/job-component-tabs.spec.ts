import { describe, expect, it } from 'vitest'
import {
  firstJobDocumentSection,
  isFixedJobWorkspaceSection,
  jobComponentSectionsFromGroups,
  jobWorkspaceSectionList,
  resolveGroupTemplate,
} from '../app/utils/freight/job-component-tabs'

const JOB_CORE_IDS = ['overview', 'route', 'containers', 'finance', 'files']

const groups = [
  { code: 'OVERVIEW', name: 'Overview', displayOrder: 1, showOnJobWorkspace: 'Yes', status: 'Active' },
  { code: 'INVOICE', name: 'Invoice', displayOrder: 10, showOnJobWorkspace: 'Yes', status: 'Active' },
  { code: 'CUSTOMS', name: 'Customs', displayOrder: 50, showOnJobWorkspace: 'Yes', status: 'Active' },
  { code: 'FILES', name: 'Files', displayOrder: 90, showOnJobWorkspace: 'Yes', status: 'Active' },
  { code: 'HIDDEN', name: 'Hidden', displayOrder: 5, showOnJobWorkspace: 'No', status: 'Active' },
]

const assignments = [
  { tradeDirection: 'Import', componentGroup: 'Invoice', componentTemplate: 'Commercial Invoice', status: 'Active', displayOrder: 10 },
  { tradeDirection: 'Export', componentGroup: 'Customs', componentTemplate: 'Customs Clearance', status: 'Active', displayOrder: 50 },
]

describe('job workspace core vs component-group tabs', () => {
  it('always keeps overview, route, containers, finance, and files', () => {
    expect(jobWorkspaceSectionList([])).toEqual(['overview', 'route', 'containers', 'finance', 'files'])
    expect(jobWorkspaceSectionList(undefined)).toEqual(['overview', 'route', 'containers', 'finance', 'files'])
    expect(JOB_CORE_IDS.every(id => isFixedJobWorkspaceSection(id))).toBe(true)
  })

  it('builds extra tabs from component groups and skips reserved codes', () => {
    expect(jobComponentSectionsFromGroups(groups)).toEqual(['invoice', 'customs'])
    expect(jobWorkspaceSectionList(groups)).toEqual([
      'overview',
      'route',
      'containers',
      'invoice',
      'customs',
      'finance',
      'files',
    ])
  })

  it('filters extra tabs by trade-direction assignment when the group is assigned', () => {
    expect(jobComponentSectionsFromGroups(groups, { direction: 'Import', assignments })).toEqual(['invoice'])
    expect(jobComponentSectionsFromGroups(groups, { direction: 'Export', assignments })).toEqual(['customs'])
  })

  it('resolves the template from trade-direction assignment then group code', () => {
    const templates = [
      { code: 'COMMERCIAL_INVOICE', name: 'Commercial Invoice', group: 'INVOICE', status: 'Active' },
      { code: 'CUSTOMS_CLEARANCE', name: 'Customs Clearance', group: 'CUSTOMS', status: 'Active' },
    ]
    const invoice = resolveGroupTemplate({
      group: groups[1]!,
      templates,
      assignments,
      direction: 'Import',
    })
    expect(invoice?.code).toBe('COMMERCIAL_INVOICE')
    const byGroup = resolveGroupTemplate({
      group: groups[2]!,
      templates,
      assignments: [],
    })
    expect(byGroup?.code).toBe('CUSTOMS_CLEARANCE')
  })

  it('returns an empty first document section when only core tabs exist', () => {
    expect(firstJobDocumentSection([])).toBe('')
    expect(firstJobDocumentSection(groups)).toBe('invoice')
  })
})
