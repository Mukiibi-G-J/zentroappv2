'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Building2, Loader2 } from 'lucide-react'
import { OtpInput } from '@/components/auth/OtpInput'
import { setAccessTokenCookie } from '@/lib/api'
import { applyLoginBranchState } from '@/lib/loginBranch'
import { readVerifyOtpQueryParams } from '@/lib/postSignupSession'
import { writeStoredSession } from '@/lib/session'
import { isMainAppHost } from '@/lib/tenantUrl'
import { resolvePostLoginPath } from '@/lib/postLoginRedirect'
import { fetchAuthSession, resendOtp, verifyOtp } from '@/services/auth.service'
import type { OtpChannel } from '@/types/auth'

const RESEND_COOLDOWN_SECONDS = 60

function formatOtpDestination(email: string, channel: OtpChannel): string {
  if (channel === 'sms') return 'your phone'
  if (channel === 'both') return `${email} and your phone`
  return email
}

function VerifyOtpForm() {
  const searchParams = useSearchParams()
  const queryString = searchParams.toString()
  const queryParams = useMemo(() => readVerifyOtpQueryParams(queryString), [queryString])

  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(RESEND_COOLDOWN_SECONDS)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  const email = queryParams.email
  const otpChannel: OtpChannel = queryParams.otpChannel ?? 'email'

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (isMainAppHost(window.location.hostname)) {
      window.location.replace('/workspace')
      return
    }
    setReady(true)
  }, [])

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = window.setTimeout(() => {
      setResendCooldown((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [resendCooldown])

  const finalizeSession = async (access: string, refresh: string) => {
    localStorage.setItem('access_token', access)
    setAccessTokenCookie(access)
    if (refresh) localStorage.setItem('refresh_token', refresh)

    try {
      const session = await fetchAuthSession()
      writeStoredSession(session)
      applyLoginBranchState(access, session)
    } catch {
      applyLoginBranchState(access, null)
    }

    window.location.replace(resolvePostLoginPath(access))
  }

  const handleVerify = async (otp: string) => {
    if (!email) return
    setLoading(true)
    setError(null)
    try {
      const data = await verifyOtp(otp, email)
      if (!data.access || !data.refresh) {
        throw new Error('Missing session tokens after verification')
      }
      await finalizeSession(data.access, data.refresh)
    } catch {
      setError('Invalid verification code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (resendCooldown > 0 || resending || !email) return
    setResending(true)
    setError(null)
    try {
      await resendOtp({
        email,
        channel: otpChannel === 'sms' ? 'sms' : 'email',
      })
      setResendCooldown(RESEND_COOLDOWN_SECONDS)
    } catch {
      setError('Failed to resend code. Please try again.')
    } finally {
      setResending(false)
    }
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-s1/5 via-white to-s2/5">
        <Loader2 className="h-8 w-8 animate-spin text-s1" />
      </div>
    )
  }

  if (!email) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-s1/5 via-white to-s2/5 p-4">
        <div className="max-w-md rounded-lg border border-strokeColor bg-white p-8 text-center">
          <p className="text-bodyText">Missing email for verification. Sign in again to receive a new code.</p>
          <a href="/login" className="mt-4 inline-block text-s1 font-medium hover:text-s2">
            Go to sign in
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-strokeColor bg-white p-8 shadow-sm">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-s1 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-mainTextColor mb-2">Verify your account</h1>
          <p className="text-bodyText text-sm">
            {queryParams.isPostSignup
              ? 'Your workspace is ready — enter the code we sent you.'
              : 'Enter the verification code we sent you.'}
          </p>
        </div>

        <p className="mb-6 text-center text-sm text-bodyText">
          Code sent to {formatOtpDestination(email, otpChannel)}
        </p>

        <OtpInput length={6} onComplete={handleVerify} disabled={loading} />

        {error && (
          <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
        )}

        <div className="mt-6 text-center text-sm text-bodyText">
          Didn&apos;t receive the code?{' '}
          {resending ? (
            <span>Sending…</span>
          ) : resendCooldown > 0 ? (
            <span>Resend in {resendCooldown}s</span>
          ) : (
            <button
              type="button"
              onClick={handleResend}
              className="font-semibold text-s1 hover:text-s2"
            >
              Resend
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function VerifyOtpPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading…</div>}>
      <VerifyOtpForm />
    </Suspense>
  )
}
