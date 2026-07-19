/** Public desktop installer download URLs for marketing pages. */

function publicApiOrigin(): string {
  if (process.env.NODE_ENV === 'development') {
    const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
    return `http://localhost:${port}`
  }
  const apiHost =
    process.env.NEXT_PUBLIC_API_HOST ?? 'zentroapp-backend.com'
  return `https://${apiHost}`
}

/**
 * Windows desktop installer — backend /download/windows/ (latest active windows AppVersion),
 * or override with NEXT_PUBLIC_DESKTOP_WINDOWS_URL.
 */
export const DESKTOP_WINDOWS_DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_DESKTOP_WINDOWS_URL?.trim() ||
  `${publicApiOrigin()}/download/windows/`
