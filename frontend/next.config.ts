import type { NextConfig } from 'next'

const apiPort = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
const apiUrl = process.env.NEXT_PUBLIC_API_URL
// Prefer 127.0.0.1. If Cursor (or another tool) port-forwards loopback:8002 to a remote
// HTTPS API, set NEXT_PUBLIC_API_REWRITE_HOST to a LAN IP that reaches local Django
// (e.g. the host IP shown by `ipconfig` that returns 200 on :8002).
const apiRewriteHost = process.env.NEXT_PUBLIC_API_REWRITE_HOST ?? '127.0.0.1'

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  // Without this, Next 308-strips /api/.../ before the rewrite below, then Django
  // APPEND_SLASH 301-adds it back → infinite redirect. signup defaults fail that way.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Local next-dev proxy only. On Vercel the browser calls the API host directly.
    if (process.env.VERCEL || apiUrl) return []
    // Two patterns: Next otherwise strips the trailing slash before proxying to Django,
    // which breaks POST (APPEND_SLASH cannot redirect while keeping the body).
    return [
      {
        source: '/api/:path*/',
        destination: `http://${apiRewriteHost}:${apiPort}/api/:path*/`,
      },
      {
        source: '/api/:path*',
        destination: `http://${apiRewriteHost}:${apiPort}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
