import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'

const USERS_PATH = '/administration/users'

function formFieldKeys(isCreate?: boolean): string[] {
  const module = getFreightModule(USERS_PATH)
  if (!module) throw new Error('users module is missing')
  return moduleDocumentTabs(module, { isCreate })
    .flatMap(tab => tab.sections)
    .flatMap(section => section.fields.map(field => field.key))
}

describe('user form password field', () => {
  it('asks for a required password while creating a user', () => {
    const field = getFreightModule(USERS_PATH)?.fields.find(item => item.key === 'password')
    expect(field).toMatchObject({ type: 'password', required: true, createOnly: true })
    expect(formFieldKeys(true)).toContain('password')
  })

  it('hides the password field while editing a user', () => {
    expect(formFieldKeys(false)).not.toContain('password')
  })

  it('never renders a user code input', () => {
    expect(formFieldKeys(true)).not.toContain('userCode')
    expect(formFieldKeys(false)).not.toContain('userCode')
  })
})