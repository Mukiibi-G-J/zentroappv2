'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Building2, Eye, EyeOff, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { resetPassword } from '@/services/auth.service'

function ResetPasswordForm() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [formData, setFormData] = useState({
    newPassword: '',
    confirmPassword: '',
  })
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(
    token ? null : 'Invalid or missing reset link. Please request a new password reset.',
  )
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return

    setError(null)
    if (formData.newPassword !== formData.confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (formData.newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setIsSubmitting(true)
    try {
      await resetPassword(token, formData.newPassword)
      setSuccess(true)
      window.setTimeout(() => {
        window.location.replace('/login')
      }, 2000)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? 'Failed to reset password. Please try again.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-lg border border-strokeColor bg-white text-mainTextColor shadow-sm p-8 text-center">
          <div className="w-16 h-16 bg-s1 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-mainTextColor mb-2">Invalid Reset Link</h1>
          <p className="text-bodyText mb-6">
            This password reset link is invalid or has expired. Please request a new one.
          </p>
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-left">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}
          <a href="/forgot-password" className="inline-block text-sm font-medium text-s1 hover:text-s2">
            Request New Reset Link
          </a>
          <div className="mt-4">
            <a href="/login" className="text-sm font-medium text-s1 hover:text-s2">
              Back to Sign In
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-strokeColor bg-white text-mainTextColor shadow-sm p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-s1 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-mainTextColor mb-2">Set New Password</h1>
          <p className="text-bodyText">
            Enter your new password below. Use at least 8 characters.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-700 text-sm">
              Password reset successfully! Redirecting you to sign in…
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="newPassword"
              className="block text-sm font-medium text-mainTextColor mb-2"
            >
              New Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bodyText" />
              <input
                id="newPassword"
                name="newPassword"
                type={showNew ? 'text' : 'password'}
                value={formData.newPassword}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, newPassword: e.target.value }))
                  if (error) setError(null)
                }}
                placeholder="New password"
                autoComplete="new-password"
                required
                disabled={success}
                className={cn(
                  'flex h-10 w-full rounded-lg border border-strokeColor bg-white pl-10 pr-10 py-2',
                  'text-sm text-mainTextColor placeholder:text-bodyText',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                )}
              />
              <button
                type="button"
                onClick={() => setShowNew((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-bodyText hover:text-mainTextColor"
                tabIndex={-1}
              >
                {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium text-mainTextColor mb-2"
            >
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bodyText" />
              <input
                id="confirmPassword"
                name="confirmPassword"
                type={showConfirm ? 'text' : 'password'}
                value={formData.confirmPassword}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, confirmPassword: e.target.value }))
                  if (error) setError(null)
                }}
                placeholder="Confirm new password"
                autoComplete="new-password"
                required
                disabled={success}
                className={cn(
                  'flex h-10 w-full rounded-lg border border-strokeColor bg-white pl-10 pr-10 py-2',
                  'text-sm text-mainTextColor placeholder:text-bodyText',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                )}
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-bodyText hover:text-mainTextColor"
                tabIndex={-1}
              >
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || success}
            className={cn(
              'inline-flex items-center justify-center w-full h-10 px-4 rounded-lg',
              'text-sm font-medium text-white bg-s1 hover:bg-s1/90 transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
              'disabled:opacity-50 disabled:pointer-events-none',
            )}
          >
            {isSubmitting ? 'Resetting...' : 'Reset Password'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <a href="/login" className="text-sm font-medium text-s1 hover:text-s2">
            Back to Sign In
          </a>
        </div>
      </div>
    </div>
  )
}

export function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading…</div>}>
      <ResetPasswordForm />
    </Suspense>
  )
}
