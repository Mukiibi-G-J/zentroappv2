import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  // Cursor Simple Browser often steals localhost:3000; we run on 3001 by default.
  // Allow LAN IP HMR when opening via http://10.10.10.78:3001
  allowedDevOrigins: ['10.10.10.78'],
  // Without this, Next 308-strips /api/.../ before the proxy route, then Django
  // APPEND_SLASH 301-adds it back → infinite redirect.
  skipTrailingSlashRedirect: true,
  // Local /api is handled by app/api/[...path]/route.ts (strips Cookie → avoids 431).
  // On Vercel the browser calls NEXT_PUBLIC_API_URL directly (see lib/api.ts).
}

export default nextConfig
