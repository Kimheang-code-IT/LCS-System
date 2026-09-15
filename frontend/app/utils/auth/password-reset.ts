const STORAGE_KEY = 'lcs-freight:auth:password-reset'

export interface PasswordResetSession {
  email: string
  verified: boolean
  /** Stored after successful verify so reset-password can submit without re-entry. */
  code?: string
  updatedAt: string
}

function readRaw(): PasswordResetSession | null {
  if (!import.meta.client) return null
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as PasswordResetSession
  }
  catch {
    return null
  }
}

function writeRaw(session: PasswordResetSession | null) {
  if (!import.meta.client) return
  if (!session) {
    sessionStorage.removeItem(STORAGE_KEY)
    return
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

/** Persist the email after "send reset code". */
export function startPasswordReset(email: string) {
  writeRaw({
    email: email.trim().toLowerCase(),
    verified: false,
    updatedAt: new Date().toISOString(),
  })
}

export function getPasswordResetSession(): PasswordResetSession | null {
  return readRaw()
}

export function markPasswordResetVerified(code: string) {
  const current = readRaw()
  if (!current?.email) return null
  const next: PasswordResetSession = {
    ...current,
    verified: true,
    code: String(code || '').trim(),
    updatedAt: new Date().toISOString(),
  }
  writeRaw(next)
  return next
}

export function clearPasswordResetSession() {
  writeRaw(null)
}
