/** Stash/restore debug_admin tokens while viewing as another user. */

const ADMIN_ACCESS_KEY = 'impersonation_admin_access'
const ADMIN_REFRESH_KEY = 'impersonation_admin_refresh'
const META_KEY = 'impersonation_meta'

export type ImpersonationMeta = {
  active: boolean
  target: {
    id: number
    fullName: string
    username: string
    email: string
  }
  impersonator: {
    id: number
    username: string
  }
}

export function hasStashedAdminSession(): boolean {
  if (typeof window === 'undefined') return false
  return Boolean(localStorage.getItem(ADMIN_ACCESS_KEY))
}

export function readImpersonationMeta(): ImpersonationMeta | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(META_KEY)
    if (!raw) return null
    return JSON.parse(raw) as ImpersonationMeta
  } catch {
    return null
  }
}

export function stashAdminSession(meta: ImpersonationMeta): void {
  if (typeof window === 'undefined') return
  const access = localStorage.getItem('access_token')
  const refresh = localStorage.getItem('refresh_token')
  if (access) localStorage.setItem(ADMIN_ACCESS_KEY, access)
  if (refresh) localStorage.setItem(ADMIN_REFRESH_KEY, refresh)
  localStorage.setItem(META_KEY, JSON.stringify(meta))
}

export function restoreAdminSession(): boolean {
  if (typeof window === 'undefined') return false
  const access = localStorage.getItem(ADMIN_ACCESS_KEY)
  const refresh = localStorage.getItem(ADMIN_REFRESH_KEY)
  if (!access) return false
  localStorage.setItem('access_token', access)
  if (refresh) {
    localStorage.setItem('refresh_token', refresh)
  } else {
    localStorage.removeItem('refresh_token')
  }
  clearImpersonationStash()
  return true
}

export function clearImpersonationStash(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(ADMIN_ACCESS_KEY)
  localStorage.removeItem(ADMIN_REFRESH_KEY)
  localStorage.removeItem(META_KEY)
}

export function isImpersonationActive(): boolean {
  return hasStashedAdminSession() || Boolean(readImpersonationMeta()?.active)
}
