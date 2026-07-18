import { getApiBaseUrl } from '@/lib/apiBase'

export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  const base = getApiBaseUrl().replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}
