'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { fetchAuthSession } from '@/services/auth.service'
import { readStoredSession, writeStoredSession, clearStoredSession } from '@/lib/session'
import type { AuthSession } from '@/types/auth'

interface SessionContextValue {
  session: AuthSession | null
  isReady: boolean
  refreshSession: () => Promise<void>
  clearSession: () => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isReady, setIsReady] = useState(false)

  const refreshSession = useCallback(async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    if (!token) {
      setSession(null)
      clearStoredSession()
      setIsReady(true)
      return
    }
    try {
      const data = await fetchAuthSession()
      writeStoredSession(data)
      setSession(data)
    } catch {
      setSession(readStoredSession())
    } finally {
      setIsReady(true)
    }
  }, [])

  const clearSession = useCallback(() => {
    setSession(null)
    clearStoredSession()
  }, [])

  useEffect(() => {
    // Apply cached session only after mount so SSR HTML ("User") matches
    // the first client render before localStorage is read.
    setSession(readStoredSession())
    void refreshSession()
  }, [refreshSession])

  const value = useMemo(
    () => ({ session, isReady, refreshSession, clearSession }),
    [session, isReady, refreshSession, clearSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) {
    throw new Error('useSession must be used within SessionProvider')
  }
  return ctx
}
