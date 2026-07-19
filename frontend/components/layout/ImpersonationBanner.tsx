'use client'

import { useState } from 'react'
import { LogOut } from 'lucide-react'
import { toast } from 'sonner'
import { useSession } from '@/context/SessionContext'
import { stopImpersonation } from '@/services/auth.service'
import { readImpersonationMeta, isImpersonationActive } from '@/lib/impersonation'
import { resolvePostLoginPath } from '@/lib/postLoginRedirect'

export function ImpersonationBanner() {
  const { session } = useSession()
  const [exiting, setExiting] = useState(false)

  const meta = session?.impersonation?.active
    ? session.impersonation
    : readImpersonationMeta()

  if (!meta?.active && !isImpersonationActive()) return null
  if (!meta?.active) return null

  const targetName = meta.target.fullName || meta.target.username
  const targetUsername = meta.target.username

  const handleExit = async () => {
    if (exiting) return
    setExiting(true)
    try {
      await stopImpersonation()
      const access = localStorage.getItem('access_token') || ''
      toast.success('Returned to debug_admin session')
      window.location.replace(access ? resolvePostLoginPath(access) : '/dashboard')
    } catch (err) {
      toast.error('Failed to exit impersonation')
      console.error(err)
      setExiting(false)
    }
  }

  return (
    <div
      className="flex items-center justify-between gap-3 border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-950"
      role="status"
      title="You are viewing the system as another user. Logout will end both sessions."
    >
      <p className="min-w-0 truncate">
        Viewing as <span className="font-semibold">{targetName}</span>
        {targetUsername ? (
          <>
            {' '}
            (<span className="font-mono text-xs">{targetUsername}</span>)
          </>
        ) : null}
      </p>
      <button
        type="button"
        onClick={() => void handleExit()}
        disabled={exiting}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-400 bg-white px-3 py-1 text-sm font-medium text-amber-950 transition hover:bg-amber-100 disabled:opacity-60"
      >
        <LogOut size={14} />
        {exiting ? 'Exiting…' : 'Exit'}
      </button>
    </div>
  )
}
