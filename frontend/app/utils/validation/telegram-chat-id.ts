/** Numeric Telegram chat IDs (JSON int, no leading zeros/+; groups are negative). */
export function isValidTelegramChatId(value: string): boolean {
  const raw = value.trim()
  if (!/^-?\d+$/.test(raw) || raw.startsWith('-0') || raw.startsWith('+')) return false
  // Chat IDs are transported as JSON numbers; beyond 2^53 they lose precision.
  return Math.abs(Number(raw)) < 2 ** 53
}

/** Client groups are negative group/supergroup chats. */
export function isValidTelegramGroupChatId(value: string): boolean {
  return value.trim().startsWith('-') && isValidTelegramChatId(value)
}

/** Admin destinations are positive private chats. */
export function isValidTelegramPrivateChatId(value: string): boolean {
  return !value.trim().startsWith('-') && isValidTelegramChatId(value)
}
