'use client'

import { useState } from 'react'
import { Building2, Mail } from 'lucide-react'
import { cn } from '@/lib/utils'
import { forgotPassword } from '@/services/auth.service'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [emailSent, setEmailSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    try {
      await forgotPassword(email)
      setEmailSent(true)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? 'Failed to send reset email. Please try again.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-strokeColor bg-white text-mainTextColor shadow-sm p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-s1 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          {emailSent ? (
            <>
              <h1 className="text-2xl font-bold text-mainTextColor mb-2">Check Your Email</h1>
              <p className="text-bodyText">
                If an account exists with the email you entered, you will receive a password
                reset link. The link expires in 1 hour.
              </p>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-mainTextColor mb-2">Forgot Password</h1>
              <p className="text-bodyText">
                Enter your email address and we&apos;ll send you a link to reset your password.
              </p>
            </>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        {emailSent ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-bodyText">
              Didn&apos;t receive the email? Check your spam folder or{' '}
              <button
                type="button"
                onClick={() => {
                  setEmailSent(false)
                  setError(null)
                }}
                className="font-medium text-s1 hover:text-s2"
              >
                try again
              </button>
              .
            </p>
            <a href="/login" className="inline-block text-sm font-medium text-s1 hover:text-s2">
              Back to Sign In
            </a>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-mainTextColor mb-2"
              >
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bodyText" />
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (error) setError(null)
                  }}
                  placeholder="you@company.com"
                  autoComplete="email"
                  required
                  className={cn(
                    'flex h-10 w-full rounded-lg border border-strokeColor bg-white pl-10 pr-3 py-2',
                    'text-sm text-mainTextColor placeholder:text-bodyText',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'inline-flex items-center justify-center w-full h-10 px-4 rounded-lg',
                'text-sm font-medium text-white bg-s1 hover:bg-s1/90 transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                'disabled:opacity-50 disabled:pointer-events-none',
              )}
            >
              {isSubmitting ? 'Sending...' : 'Send Reset Link'}
            </button>

            <p className="text-center text-sm text-bodyText">
              Remember your password?{' '}
              <a href="/login" className="font-medium text-s1 hover:text-s2">
                Sign In
              </a>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
