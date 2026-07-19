/**
 * Local tenant hosts (.localhost) often accumulate huge cookies (legacy JWT
 * cookies, Django admin session, etc.). Next then proxies them to Django and
 * Node/gunicorn returns 431 Request Header Fields Too Large.
 */

const LEGACY_AUTH_COOKIE_NAMES = [
  'access_token',
  'refresh_token',
  'auth_session',
] as const

function expireCookie(name: string, domain?: string): void {
  const domainPart = domain ? `; domain=${domain}` : ''
  document.cookie = `${name}=; path=/${domainPart}; max-age=0; SameSite=Lax`
}

function candidateDomains(hostname: string): Array<string | undefined> {
  const domains: Array<string | undefined> = [undefined, hostname, `.${hostname}`]
  const parts = hostname.split('.')
  if (parts.length >= 2) {
    const parent = parts.slice(1).join('.')
    domains.push(parent, `.${parent}`)
  }
  // Chrome treats *.localhost specially; also clear bare .localhost
  if (hostname.endsWith('.localhost') || hostname === 'localhost') {
    domains.push('localhost', '.localhost')
  }
  return [...new Set(domains)]
}

/** Drop known auth cookies that should live in localStorage, not Cookie. */
export function clearLegacyAuthCookies(): void {
  if (typeof document === 'undefined') return
  const domains = candidateDomains(window.location.hostname)
  for (const name of LEGACY_AUTH_COOKIE_NAMES) {
    for (const domain of domains) {
      expireCookie(name, domain)
    }
  }
}

/** Expire any cookie whose value alone is oversized. */
export function clearOversizedCookies(maxValueLength = 400): void {
  if (typeof document === 'undefined') return
  const raw = document.cookie
  if (!raw) return

  const domains = candidateDomains(window.location.hostname)
  for (const part of raw.split(';')) {
    const eq = part.indexOf('=')
    if (eq < 0) continue
    const name = part.slice(0, eq).trim()
    const value = part.slice(eq + 1).trim()
    if (!name) continue
    if (value.length <= maxValueLength && !LEGACY_AUTH_COOKIE_NAMES.includes(name as (typeof LEGACY_AUTH_COOKIE_NAMES)[number])) {
      continue
    }
    for (const domain of domains) {
      expireCookie(name, domain)
    }
  }
}

export function clearCookiesThatCause431(): void {
  clearLegacyAuthCookies()
  clearOversizedCookies()
}
