import { decodeJwtPayload } from '@/lib/jwt'

interface JwtPasswordClaims {
  must_change_password?: boolean
}

export function mustChangePasswordFromToken(accessToken: string): boolean {
  try {
    const claims = decodeJwtPayload<JwtPasswordClaims>(accessToken)
    return claims.must_change_password === true
  } catch {
    return false
  }
}

export function resolvePostLoginPath(
  accessToken: string,
  options?: { mustChangePassword?: boolean; redirectTo?: string | null },
): string {
  const mustChange =
    options?.mustChangePassword === true || mustChangePasswordFromToken(accessToken)
  if (mustChange) return '/change-password'

  const redirectTo = options?.redirectTo
  if (redirectTo && redirectTo.startsWith('/') && !redirectTo.startsWith('//')) {
    return redirectTo
  }
  return '/dashboard'
}
