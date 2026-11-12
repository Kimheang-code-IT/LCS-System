/**
 * Deterministic default avatar: initials on a stable colour, inlined as a data
 * URI. An external avatar service would need a CSP `img-src` exception (and a
 * third-party request for every user), so the fallback stays self-contained.
 */
export function defaultUserAvatarUrl(name?: string) {
  const label = (name || 'User').trim() || 'User'
  const initials = label
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0] || '')
    .join('')
    .toUpperCase()
  const hue = [...label].reduce((acc, char) => (acc * 31 + (char.codePointAt(0) || 0)) % 360, 7)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">`
    + `<rect width="64" height="64" rx="32" fill="hsl(${hue} 55% 45%)"/>`
    + `<text x="32" y="32" dy=".35em" text-anchor="middle" font-family="sans-serif" `
    + `font-size="26" fill="#ffffff">${escapeXml(initials)}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function escapeXml(value: string) {
  return value.replace(/[<>&"']/g, char => `&#${char.charCodeAt(0)};`)
}

export function resolveUserAvatar(user?: { name?: string, avatar?: string } | null) {
  return user?.avatar || defaultUserAvatarUrl(user?.name)
}
