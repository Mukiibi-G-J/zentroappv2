import type { AuthSession } from '@/types/auth'

const SESSION_KEY = 'auth_session'

export function readStoredSession(): AuthSession | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return JSON.parse(raw) as AuthSession
  } catch {
    return null
  }
}

export function writeStoredSession(session: AuthSession): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearStoredSession(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(SESSION_KEY)
}

export function getRoleCentrePageId(): number | null {
  return readStoredSession()?.roleCentrePageId ?? null
}
