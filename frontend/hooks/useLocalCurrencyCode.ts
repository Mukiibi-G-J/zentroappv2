'use client'

import { useSession } from '@/context/SessionContext'
import { decodeJwtPayload } from '@/lib/jwt'

const DEFAULT_LOCAL_CURRENCY = 'UGX'

interface JwtCurrencyClaims {
  local_currency_code?: string
}

/** Local currency from GL Setup via auth session, with JWT fallback. */
export function useLocalCurrencyCode(): string {
  const { session } = useSession()
  const fromSession = session?.localCurrencyCode?.trim()
  if (fromSession) return fromSession.toUpperCase()

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        const claims = decodeJwtPayload<JwtCurrencyClaims>(token)
        const fromJwt = claims.local_currency_code?.trim()
        if (fromJwt) return fromJwt.toUpperCase()
      } catch {
        // ignore invalid token
      }
    }
  }

  return DEFAULT_LOCAL_CURRENCY
}
