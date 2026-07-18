'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, User } from 'lucide-react'
import { useSession } from '@/context/SessionContext'

interface POSFullscreenShellProps {
  title: string
  children: ReactNode
}

export function POSFullscreenShell({ title, children }: POSFullscreenShellProps) {
  const router = useRouter()
  const { session } = useSession()

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') router.push('/dashboard')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [router])

  const displayName = session?.user.fullName || 'User'

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-softBg">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-strokeColor bg-white px-4 sm:px-5">
        <button
          type="button"
          onClick={() => router.push('/dashboard')}
          className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-bodyText transition hover:bg-softBg hover:text-mainTextColor"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Exit POS</span>
        </button>

        <div className="min-w-0 flex-1 text-center sm:text-left">
          <p className="truncate text-base font-semibold text-mainTextColor">{title}</p>
        </div>

        <div className="flex items-center gap-2 text-sm text-bodyText">
          <User className="h-4 w-4 shrink-0" />
          <span className="hidden max-w-[140px] truncate sm:inline">{displayName}</span>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col overflow-hidden p-3 sm:p-4">{children}</main>
    </div>
  )
}
