'use client'

import { useState } from 'react'
import { Lock, Eye, EyeOff } from 'lucide-react'
import api, { setAccessTokenCookie } from '@/lib/api'
import { resolvePostLoginPath } from '@/lib/postLoginRedirect'

export function ChangePasswordPage() {
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (formData.newPassword !== formData.confirmPassword) {
      setError('New passwords do not match.')
      return
    }
    if (formData.newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await api.post<{
        message: string
        access?: string
        refresh?: string
      }>('/api/auth/change-password/', {
        current_password: formData.currentPassword,
        new_password: formData.newPassword,
        confirm_password: formData.confirmPassword,
      })

      if (res.data.access) {
        localStorage.setItem('access_token', res.data.access)
        setAccessTokenCookie(res.data.access)
      }
      if (res.data.refresh) {
        localStorage.setItem('refresh_token', res.data.refresh)
      }

      const access = res.data.access ?? localStorage.getItem('access_token')
      window.location.replace(access ? resolvePostLoginPath(access) : '/dashboard')
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? 'Failed to change password. Please try again.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-s1/10 text-s1">
            <Lock size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-mainTextColor">Change your password</h1>
            <p className="text-sm text-bodyText">Your administrator requires a new password before you continue.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-bodyText">Current password</label>
            <div className="relative">
              <input
                type={showCurrent ? 'text' : 'password'}
                required
                value={formData.currentPassword}
                onChange={(e) => setFormData((prev) => ({ ...prev, currentPassword: e.target.value }))}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 pr-10 text-sm focus:border-s1 focus:outline-none focus:ring-2 focus:ring-s1/20"
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400"
                onClick={() => setShowCurrent((v) => !v)}
                aria-label={showCurrent ? 'Hide current password' : 'Show current password'}
              >
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-bodyText">New password</label>
            <div className="relative">
              <input
                type={showNew ? 'text' : 'password'}
                required
                value={formData.newPassword}
                onChange={(e) => setFormData((prev) => ({ ...prev, newPassword: e.target.value }))}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 pr-10 text-sm focus:border-s1 focus:outline-none focus:ring-2 focus:ring-s1/20"
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400"
                onClick={() => setShowNew((v) => !v)}
                aria-label={showNew ? 'Hide new password' : 'Show new password'}
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-bodyText">Confirm new password</label>
            <input
              type="password"
              required
              value={formData.confirmPassword}
              onChange={(e) => setFormData((prev) => ({ ...prev, confirmPassword: e.target.value }))}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-s1 focus:outline-none focus:ring-2 focus:ring-s1/20"
            />
          </div>

          {error && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-s1 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-s1/90 disabled:opacity-60"
          >
            {isSubmitting ? 'Saving…' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  )
}
