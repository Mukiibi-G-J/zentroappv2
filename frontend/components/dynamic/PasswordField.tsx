'use client'

import { useState } from 'react'
import { Eye, EyeOff, MoreHorizontal, X } from 'lucide-react'
import { toast } from 'sonner'

interface Props {
  value?: string | null
  disabled?: boolean
  saveFirstHint?: string
  onSave: (password: string) => void | Promise<void>
}

export default function PasswordField({ value, disabled, saveFirstHint, onSave }: Props) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [saving, setSaving] = useState(false)

  const display = value ? String(value) : ''

  const openModal = () => {
    if (disabled) {
      if (saveFirstHint) toast.error(saveFirstHint)
      return
    }
    setPassword('')
    setConfirm('')
    setOpen(true)
  }

  const closeModal = () => {
    if (saving) return
    setOpen(false)
  }

  const handleOk = async () => {
    if (!password) {
      toast.error('Enter a password.')
      return
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      toast.error('Passwords do not match.')
      return
    }
    setSaving(true)
    try {
      await onSave(password)
      setOpen(false)
      toast.success('Password updated')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not update password'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="flex gap-1">
        <input
          type="text"
          readOnly
          value={display}
          disabled={disabled}
          placeholder={disabled ? 'Save user first…' : '••••••••'}
          className="flex-1 min-w-0 px-3 py-1.5 text-sm text-mainTextColor border border-gray-200 rounded-lg bg-gray-50 disabled:text-gray-400 font-mono tracking-widest"
        />
        <button
          type="button"
          onClick={openModal}
          disabled={disabled}
          title={disabled ? saveFirstHint ?? 'Save user first' : 'Enter password'}
          className={`shrink-0 px-2.5 py-1.5 text-sm border rounded-lg transition ${
            disabled
              ? 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
              : 'border-gray-200 bg-white hover:bg-s1/5 hover:border-s1 cursor-pointer'
          }`}
        >
          <MoreHorizontal size={16} className="text-bodyText" />
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold text-mainTextColor">Enter Password</h3>
              <button
                type="button"
                onClick={closeModal}
                className="p-1 rounded hover:bg-gray-100 text-bodyText"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="px-5 py-5 space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-bodyText">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2 pr-10 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-s1/30 focus:border-s1"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-bodyText hover:text-mainTextColor"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-bodyText">Confirm Password</label>
                <div className="relative">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    className="w-full px-3 py-2 pr-10 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-s1/30 focus:border-s1"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-bodyText hover:text-mainTextColor"
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
              <button
                type="button"
                onClick={handleOk}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-s1 text-white hover:bg-s1/90 disabled:opacity-60 transition"
              >
                OK
              </button>
              <button
                type="button"
                onClick={closeModal}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-200 text-bodyText hover:bg-white transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
