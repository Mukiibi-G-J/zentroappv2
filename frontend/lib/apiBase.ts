function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL

  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'

  // Browser: same-origin /api → Next.js rewrite → Django (see next.config.ts).
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  const host = process.env.NEXT_PUBLIC_API_REWRITE_HOST ?? '127.0.0.1'
  return `http://${host}:${port}`
}

export { getApiBaseUrl }
