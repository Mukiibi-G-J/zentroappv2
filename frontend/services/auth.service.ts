import api from '@/lib/api'
import type { AuthSession, OtpChannel } from '@/types/auth'

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
