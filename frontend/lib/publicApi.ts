import axios from 'axios'

function getPublicApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL

  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
  const rewriteHost = process.env.NEXT_PUBLIC_API_REWRITE_HOST

  // When Cursor (or similar) port-forwards 127.0.0.1:8002 to a remote HTTPS API,
  // Next rewrites must use a LAN IP. Hitting that host from the browser too
  // bypasses Next's trailing-slash 308 ↔ Django APPEND_SLASH 301 redirect loop
  // (and avoids Chrome caching those permanent redirects forever).
  if (rewriteHost) {
    return `http://${rewriteHost}:${port}`
  }

  // Browser: same-origin /api → Next.js rewrite → Django (avoids cross-port CORS/PNA).
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  return `http://127.0.0.1:${port}`
}

/** Axios instance for public marketing endpoints (no auth redirect). */
const publicApi = axios.create({
  headers: { 'Content-Type': 'application/json' },
  // Never follow redirects — a 301/308 loop must surface as an error, not hang.
  maxRedirects: 0,
  validateStatus: (status) => status >= 200 && status < 300,
})

publicApi.interceptors.request.use((config) => {
  config.baseURL = getPublicApiBaseUrl()
  return config
})

export default publicApi
