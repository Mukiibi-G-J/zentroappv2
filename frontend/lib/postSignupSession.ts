import { buildTenantAppUrl } from '@/lib/tenantUrl'
import type { OtpChannel } from '@/types/auth'

export function readVerifyOtpQueryParams(search: string): {
  email: string
  otpChannel?: OtpChannel
  isPostSignup: boolean
} {
  const params = new URLSearchParams(search)
  const email = (params.get('email') || '').trim()
  const rawChannel = (params.get('otp_channel') || '').trim()
  const otpChannel =
    rawChannel === 'email' || rawChannel === 'sms' || rawChannel === 'both'
      ? rawChannel
      : undefined
  return {
    email,
    otpChannel,
    isPostSignup: params.get('setup') === '1',
  }
}

/** After company creation: open the tenant login page (email prefilled when available). */
export function redirectToTenantLoginAfterSignup(tenant: string, email?: string): void {
  const slug = tenant.trim().toLowerCase()
  const params = new URLSearchParams()
  const trimmedEmail = email?.trim()
  if (trimmedEmail) params.set('email', trimmedEmail)
  params.set('setup', '1')

  const query = params.toString()
  const path = query ? `/login?${query}` : '/login'
  const target = buildTenantAppUrl(slug, path)
  if (!target) {
    throw new Error('Could not build workspace login URL')
  }
  window.location.assign(target)
}
