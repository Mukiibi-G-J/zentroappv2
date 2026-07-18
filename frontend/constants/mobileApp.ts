/** Public APK download — production URL on deployed marketing pages. */

function publicApiOrigin(): string {
  if (process.env.NODE_ENV === 'development') {
    const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
    return `http://localhost:${port}`
  }
  const apiHost =
    process.env.NEXT_PUBLIC_API_HOST ?? 'zentroapp-api.uncodedsolutions.com'
  return `https://${apiHost}`
}

export const ANDROID_APK_DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_ANDROID_DOWNLOAD_URL?.trim() ||
  `${publicApiOrigin()}/download/`
