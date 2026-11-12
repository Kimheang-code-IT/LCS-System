import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpTelegramRepository } from '../app/repositories/http/telegram'
import { validateFieldValue } from '../app/utils/validation/field-rules'
import { isValidTelegramChatId, isValidTelegramGroupChatId, isValidTelegramPrivateChatId } from '../app/utils/validation/telegram-chat-id'
import { takeRecoveryToken, validateRecoveryForm } from '../app/utils/auth/recovery'
import { systemSettingsTabs } from '~/config/settings-schemas'

afterEach(() => vi.unstubAllGlobals())

describe('Telegram settings tab shape', () => {
  it('keeps only the shared Bot Token as a General field', () => {
    const tab = systemSettingsTabs.find(item => item.id === 'telegram')
    const keys = tab?.sections.flatMap(section => section.fields.map(field => field.key)) ?? []
    expect(keys).toEqual(['telegram.botToken'])
  })

  it('validates group (negative) and private (positive) chat ids like the backend', () => {
    expect(isValidTelegramChatId('-1001234567890')).toBe(true)
    expect(isValidTelegramChatId('+100')).toBe(false)
    expect(isValidTelegramChatId('-0123')).toBe(false)
    expect(isValidTelegramChatId('not-a-chat')).toBe(false)
    expect(isValidTelegramChatId(`-${2 ** 53}`)).toBe(false)
    expect(isValidTelegramGroupChatId('-1001234567890')).toBe(true)
    expect(isValidTelegramGroupChatId('123')).toBe(false)
    expect(isValidTelegramPrivateChatId('123456789')).toBe(true)
    expect(isValidTelegramPrivateChatId('-10012')).toBe(false)
  })
})

describe('Telegram repository workflows', () => {
  it('removes the recovery fragment and retains no token in browser storage', () => {
    const token = 'x'.repeat(43)
    const replaceState = vi.fn()
    expect(takeRecoveryToken({ hash: `#token=${token}`, pathname: '/auth/reset-password', search: '' }, { replaceState })).toBe(token)
    expect(replaceState).toHaveBeenCalledWith(null, '', '/auth/reset-password')
    expect(takeRecoveryToken({ hash: '#token=short', pathname: '/auth/reset-password', search: '' }, { replaceState })).toBe('')
  })

  it('accepts a username and rejects weak or mismatched passwords through shared validation', () => {
    expect(validateRecoveryForm({ identifier: 'operator' }, key => key)).toEqual([])
    expect(validateRecoveryForm({ password: 'weak', passwordConfirmation: 'different' }, key => key).map(f => f.key)).toEqual(['password', 'passwordConfirmation'])
  })
  it('uses server-verified group candidates instead of accepting a chat id', async () => {
    const post = vi.fn().mockResolvedValue({ data: { challenge: 'challenge', expiresAt: '2026-10-24' } })
    const get = vi.fn().mockResolvedValue({ data: { name: 'Private admins', verified: true } })
    vi.stubGlobal('useApi', () => ({ post, get }))
    const repo = createHttpTelegramRepository()
    const pair = await repo.pairGroup()
    expect(pair.challenge).toBe('challenge')
    expect((await repo.candidate()).verified).toBe(true)
    await repo.confirmGroup(pair.challenge)
    expect(post).toHaveBeenLastCalledWith('/api/v1/settings/telegram/group/confirm', { challenge: 'challenge' })
  })

  it('requires password proof for both private link changes', async () => {
    const post = vi.fn().mockResolvedValue({ data: {} })
    vi.stubGlobal('useApi', () => ({ post }))
    const repo = createHttpTelegramRepository()
    await repo.pairPrivate('current-password')
    await repo.disconnectPrivate('current-password')
    expect(post.mock.calls.map(call => call[1])).toEqual([{ current_password: 'current-password' }, { current_password: 'current-password' }])
    expect(post.mock.calls.every(call => !('user_id' in call[1]))).toBe(true)
  })

  it('exposes the bot identity with the connection status for permitted profiles', async () => {
    const get = vi.fn().mockResolvedValue({ data: { connected: true, displayName: 'Admin', username: 'tester', telegramUserId: 123, verifiedAt: '2026-11-10', blocked: false, botName: 'LCS Bot', botUsername: 'lcs_test_bot' } })
    vi.stubGlobal('useApi', () => ({ get }))
    const link = await createHttpTelegramRepository().myLink()
    expect(link.botUsername).toBe('lcs_test_bot')
    expect(link.botName).toBe('LCS Bot')
    expect(link.connected).toBe(true)
    expect(link.telegramUserId).toBe(123)
    expect(link.username).toBe('tester')
  })

  it('requests a six-digit verification command from the existing profile API', async () => {
    const post = vi.fn().mockResolvedValue({ data: { code: '123456', expiresAt: '2026-11-10T10:05:00Z', botUsername: 'lcs_test_bot' } })
    vi.stubGlobal('useApi', () => ({ post }))
    const code = await createHttpTelegramRepository().verificationCode()
    expect(code.code).toMatch(/^\d{6}$/)
    expect(post).toHaveBeenCalledWith('/api/v1/auth/me/telegram/verification-code', {})
  })

  it('propagates backend verification failures', async () => {
    vi.stubGlobal('useApi', () => ({ post: vi.fn().mockRejectedValue(new Error('invalid_bot_token')) }))
    await expect(createHttpTelegramRepository().registerWebhook()).rejects.toThrow('invalid_bot_token')
  })

  it('validates password proof using the shared leaf rules', () => {
    expect(validateFieldValue('', { required: true })).toEqual({ code: 'required' })
    expect(validateFieldValue('current', { required: true, maxLength: 128 })).toBeNull()
  })
})
