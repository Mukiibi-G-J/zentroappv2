import api, { setAccessTokenCookie, clearAccessTokenCookie } from '@/lib/api'
import type { AuthSession, AuthImpersonation, OtpChannel } from '@/types/auth'
import {
  clearImpersonationStash,
  restoreAdminSession,
  stashAdminSession,
  type ImpersonationMeta,
} from '@/lib/impersonation'
import { writeStoredSession, clearStoredSession } from '@/lib/session'

export async function fetchAuthSession(): Promise<AuthSession> {
  const res = await api.get<AuthSession>('/api/auth/me/')
  return res.data
}

export async function verifyOtp(
  otp: string,
  email: string,
): Promise<{ access: string; refresh: string; message: string }> {
  const res = await api.post<{ access: string; refresh: string; message: string }>(
    '/api/auth/verify-otp/',
    { otp, email: email.trim() },
  )
  return res.data
}

export async function resendOtp(payload: {
  email: string
  phone?: string
  channel?: 'email' | 'sms'
}): Promise<void> {
  await api.post('/api/auth/resend-otp/', payload)
}

export type TokenLoginResponse = {
  access: string
  refresh: string
  otp_channel?: OtpChannel
  must_change_password?: boolean
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await api.post<{ message: string }>('/api/auth/forgot-password/', {
    email: email.trim(),
  })
  return res.data
}

export async function resetPassword(
  resetToken: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await api.post<{ message: string }>('/api/auth/reset-password/', {
    reset_token: resetToken,
    new_password: newPassword,
  })
  return res.data
}

export type ImpersonateResponse = {
  access: string
  refresh: string
  session: AuthSession
  impersonation: AuthImpersonation
}

export async function impersonateUser(userId: number): Promise<ImpersonateResponse> {
  const res = await api.post<ImpersonateResponse>(`/api/users/${userId}/impersonate/`)
  return res.data
}

export async function exitImpersonationAudit(): Promise<void> {
  try {
    await api.post('/api/auth/exit-impersonation/')
  } catch {
    // Best-effort audit; client still restores admin tokens.
  }
}

/** Swap into target user session; stashes current (debug_admin) tokens. */
export async function startImpersonation(userId: number): Promise<AuthSession> {
  const data = await impersonateUser(userId)
  const meta: ImpersonationMeta = data.impersonation
  stashAdminSession(meta)
  localStorage.setItem('access_token', data.access)
  localStorage.setItem('refresh_token', data.refresh)
  setAccessTokenCookie(data.access)
  writeStoredSession(data.session)
  return data.session
}

/** Restore stashed debug_admin session and notify backend for audit. */
export async function stopImpersonation(): Promise<void> {
  await exitImpersonationAudit()
  const restored = restoreAdminSession()
  if (!restored) {
    clearImpersonationStash()
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    clearAccessTokenCookie()
    clearStoredSession()
    return
  }
  setAccessTokenCookie(localStorage.getItem('access_token') || '')
}

/** Full logout: drop target tokens and any stashed admin session. */
export function clearAllAuthIncludingImpersonation(): void {
  clearImpersonationStash()
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  clearAccessTokenCookie()
  clearStoredSession()
}
