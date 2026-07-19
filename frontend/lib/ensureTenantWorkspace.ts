import publicApi from '@/lib/publicApi'
import { buildMainAppUrl, tenantSlugFromHostname } from '@/lib/tenantUrl'
import { clearBranchSession } from '@/lib/branchSession'
import { clearStoredSession } from '@/lib/session'
import { clearImpersonationStash } from '@/lib/impersonation'

const AUTH_SESSION_COOKIE = 'auth_session'

/** Clear local auth so a bad tenant token cannot bounce the user back. */
export function clearClientAuthState(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('impersonation_admin_access')
  localStorage.removeItem('impersonation_admin_refresh')
  localStorage.removeItem('impersonation_meta')
  clearImpersonationStash()
  clearBranchSession()
  clearStoredSession()
  document.cookie = `${AUTH_SESSION_COOKIE}=; path=/; max-age=0`
}

/** Send user to the marketing workspace picker (company name check). */
export function redirectToWorkspacePicker(): void {
  if (typeof window === 'undefined') return
  clearClientAuthState()
  window.location.replace(buildMainAppUrl('/workspace'))
}

export function isUnknownTenantApiError(err: unknown): boolean {
  if (!err || typeof err !== 'object' || !('response' in err)) return false
  const response = (err as { response?: { status?: number; data?: { error?: string } } }).response
  const status = response?.status
  const message = response?.data?.error
  if (status !== 404 && status !== 400) return false
  return message === 'Unknown tenant' || message === 'No tenant in token'
}

/**
 * On a tenant subdomain, verify the company exists.
 * If not (typo like pimewise), send them to /workspace to pick a valid one.
 * Returns false when redirecting.
 */
export async function ensureTenantWorkspaceExists(): Promise<boolean> {
  if (typeof window === 'undefined') return true

  const slug = tenantSlugFromHostname(window.location.hostname)
  if (!slug) return true

  try {
    const { data } = await publicApi.post<{ is_existing: boolean }>(
      '/api/company/check-company-exists/',
      { company_name: slug },
    )
    if (data.is_existing) return true
  } catch {
    // Network/API errors: do not bounce (avoid lockout during outages).
    return true
  }

  redirectToWorkspacePicker()
  return false
}
