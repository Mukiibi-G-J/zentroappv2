/** Decode JWT payload without extra dependencies (login-time only). */
export function decodeJwtPayload<T extends object = Record<string, unknown>>(token: string): T {
  const segment = token.split('.')[1]
  if (!segment) throw new Error('Invalid token')
  const normalized = segment.replace(/-/g, '+').replace(/_/g, '/')
  const json = atob(normalized)
  return JSON.parse(json) as T
}
