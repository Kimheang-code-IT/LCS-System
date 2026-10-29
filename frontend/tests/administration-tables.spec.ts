import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'

const keys = (path: string) => getFreightModule(path)!.columns.map(column => column.key)

describe('administration tables', () => {
  it('lists users with role, last login and audit columns', () => {
    expect(keys('/administration/users')).toEqual([
      'username',
      'displayName',
      'email',
      'role',
      'status',
      'lastLogin',
      'createdBy',
      'createdAt',
    ])
  })

  it('lists roles with counts, status and audit columns', () => {
    expect(keys('/administration/roles')).toEqual([
      'name',
      'description',
      'permissionCount',
      'userCount',
      'status',
      'createdBy',
      'createdAt',
    ])
  })

  it('lists audit events as time, user, action, module, record and result', () => {
    expect(keys('/administration/audit-logs')).toEqual([
      'occurredAt',
      'user',
      'action',
      'entityType',
      'entityId',
      'result',
    ])
  })

  it('keeps the document sequence preview columns', () => {
    expect(keys('/administration/document-sequences')).toEqual([
      'documentType',
      'year',
      'prefix',
      'lastValue',
      'paddingLength',
      'nextNumberPreview',
      'status',
    ])
  })

  it('configuration versions show description, creator and publisher', () => {
    const source = readFileSync(
      fileURLToPath(new URL('../app/pages/configuration/versions/index.vue', import.meta.url)),
      'utf8',
    )
    for (const header of ['Description', 'Created By', 'Created At', 'Published By', 'Published At']) {
      expect(source).toContain(`header: '${header}'`)
    }
    expect(source).toContain('row.original.createdBy')
  })

  it('configuration versions omit the unpublished, version-count and empty-tab notices', () => {
    for (const file of ['index.vue', 'new.vue']) {
      const source = readFileSync(
        fileURLToPath(new URL(`../app/pages/configuration/versions/${file}`, import.meta.url)),
        'utf8',
      )
      expect(source, file).not.toContain('configVersions.none')
      expect(source, file).not.toContain('emptyTitle')
      expect(source, file).not.toContain('emptyDescription')
    }
    const index = readFileSync(
      fileURLToPath(new URL('../app/pages/configuration/versions/index.vue', import.meta.url)),
      'utf8',
    )
    expect(index).not.toContain('versions</UBadge>')
  })
})
