import axios from 'axios'

function getPublicApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL

  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'

  // Browser: same-origin /api → Next.js proxy → Django (avoids cross-port CORS/PNA).
  // NEXT_PUBLIC_API_REWRITE_HOST is only for the server-side proxy (route.ts), not the browser.
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  const host = process.env.NEXT_PUBLIC_API_REWRITE_HOST ?? '127.0.0.1'
  return `http://${host}:${port}`
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
