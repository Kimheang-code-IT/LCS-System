import { describe, expect, it } from 'vitest'
import { systemSettingsTabs } from '~/config/settings-schemas'

describe('backup settings schema', () => {
  it('exposes the Cloudflare R2 fields and masks the secret key', () => {
    const tab = systemSettingsTabs.find(item => item.id === 'backup')
    const fields = tab?.sections.flatMap(section => section.fields) ?? []
    const byKey = new Map(fields.map(field => [field.key, field]))

    expect(byKey.has('backup.r2AccountId')).toBe(true)
    expect(byKey.has('backup.r2AccessKeyId')).toBe(true)
    expect(byKey.get('backup.r2SecretAccessKey')?.type).toBe('secret')
    expect(byKey.has('backup.r2BucketName')).toBe(true)
    expect(byKey.has('backup.r2Endpoint')).toBe(true)
    expect(byKey.has('backup.r2Prefix')).toBe(true)
    expect(byKey.has('backup.enabled')).toBe(true)
    expect(byKey.has('backup.intervalHours')).toBe(true)
  })
})
