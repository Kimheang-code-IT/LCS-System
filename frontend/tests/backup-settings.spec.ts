import { describe, expect, it } from 'vitest'
import { systemSettingsTabs } from '~/config/settings-schemas'

describe('backup settings schema', () => {
  it('keeps exactly six tabs with Storage & Backup merged into Backup', () => {
    expect(systemSettingsTabs.map(tab => tab.id)).toEqual([
      'localization',
      'email',
      'telegram',
      'security',
      'backup',
      'maintenance',
    ])
  })

  it('exposes the canonical R2 fields and masks the secret key', () => {
    const tab = systemSettingsTabs.find(item => item.id === 'backup')
    const sectionTitles = tab?.sections.map(section => section.id) ?? []
    // DB backup schedule + the former Storage & Backup sections.
    expect(sectionTitles).toContain('backup')
    expect(sectionTitles).toContain('storageR2')
    expect(sectionTitles).toContain('storageGDrive')
    expect(sectionTitles).toContain('storagePrimary')
    const fields = tab?.sections.flatMap(section => section.fields) ?? []
    const byKey = new Map(fields.map(field => [field.key, field]))

    // Legacy duplicate backup.r2* fields are gone.
    expect(byKey.has('backup.r2AccountId')).toBe(false)
    expect(byKey.has('backup.r2AccessKeyId')).toBe(false)
    expect(byKey.has('backup.r2SecretAccessKey')).toBe(false)
    expect(byKey.has('backup.r2BucketName')).toBe(false)
    expect(byKey.has('backup.r2Endpoint')).toBe(false)
    expect(byKey.has('backup.r2Prefix')).toBe(false)
    // Canonical Object Storage fields serve both features.
    expect(byKey.get('storage.providers.r2.secretAccessKey')?.type).toBe('secret')
    expect(byKey.has('storage.providers.r2.accountId')).toBe(true)
    // The stored secret must not be statically required (blank = keep).
    expect(Boolean(byKey.get('storage.providers.r2.secretAccessKey')?.required)).toBe(false)
    expect(byKey.has('storage.providers.gdrive.authType')).toBe(true)
    expect(byKey.has('storage.primaryProvider')).toBe(true)
    expect(byKey.has('backup.enabled')).toBe(true)
    expect(byKey.has('backup.intervalHours')).toBe(true)
  })
})
