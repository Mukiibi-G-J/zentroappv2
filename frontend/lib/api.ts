import axios from 'axios'
import { clearBranchSession } from '@/lib/branchSession'
import { applyBranchHeadersToRequest } from '@/lib/branchHeaders'

function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL

  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'

  // Browser: same-origin /api → Next.js rewrite → Django.
  // Avoids calling {tenant}.localhost:8002 (often broken by Cursor port-forward on 127.0.0.1).
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  const host = process.env.NEXT_PUBLIC_API_REWRITE_HOST ?? '127.0.0.1'
  return `http://${host}:${port}`
}

const AUTH_SESSION_COOKIE = 'auth_session'

/** Lightweight cookie for Next.js middleware — full JWT stays in localStorage (often >4KB). */
export function setAccessTokenCookie(_token: string): void {
  if (typeof document === 'undefined') return
  document.cookie = `${AUTH_SESSION_COOKIE}=1; path=/; SameSite=Lax; Max-Age=86400`
}

export function clearAccessTokenCookie(): void {
  if (typeof document === 'undefined') return
  document.cookie = `${AUTH_SESSION_COOKIE}=; path=/; max-age=0`
}

const api = axios.create({
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl()
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`

    applyBranchHeadersToRequest(config)
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('access_token')
      clearBranchSession()
      clearAccessTokenCookie()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default api
