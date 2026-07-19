import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  // Without this, Next 308-strips /api/.../ before the proxy route, then Django
  // APPEND_SLASH 301-adds it back → infinite redirect.
  skipTrailingSlashRedirect: true,
  // Local /api is handled by app/api/[...path]/route.ts (strips Cookie → avoids 431).
  // On Vercel the browser calls NEXT_PUBLIC_API_URL directly (see lib/api.ts).
}

export default nextConfig
