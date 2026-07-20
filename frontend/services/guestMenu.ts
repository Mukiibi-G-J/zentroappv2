import axios from 'axios'

export interface DigitalMenuLine {
  name: string
  description: string
  price: string
  price_note: string
  is_featured: boolean
}

export interface DigitalMenuSection {
  name: string
  subtitle: string
  accent_color: string
  image_url: string
  lines: DigitalMenuLine[]
}

export interface PublicDigitalMenu {
  slug: string
  title: string
  tagline: string
  phones: string[]
  social_links: Record<string, string>
  brand_primary: string
  brand_accent: string
  currency_code: string
  logo_url: string
  cover_image_url: string
  gallery_images: string[]
  sections: DigitalMenuSection[]
}

/** Same-origin Next proxy → Django (tenant via Origin/Host). */
export async function fetchPublicDigitalMenu(
  slug = 'main',
): Promise<PublicDigitalMenu> {
  const path =
    slug === 'main'
      ? '/api/restaurant/public-menu/'
      : `/api/restaurant/public-menu/${encodeURIComponent(slug)}/`
  const { data } = await axios.get<PublicDigitalMenu>(path, { timeout: 20000 })
  return data
}

export function formatGuestMenuPrice(
  price: string | number,
  currencyCode: string,
  priceNote?: string,
): string {
  const n = typeof price === 'string' ? parseFloat(price) : price
  const formatted = Number.isFinite(n)
    ? n.toLocaleString('en-UG', { maximumFractionDigits: 0 })
    : String(price)
  const suffix = currencyCode === 'UGX' ? '/=' : ''
  const note = priceNote === '@' ? ' @' : priceNote ? ` ${priceNote}` : ''
  return `${formatted}${suffix}${note}`
}

export function getGuestMenuPageUrl(slug = 'main'): string {
  if (typeof window === 'undefined') return slug === 'main' ? '/menu' : `/menu/${slug}`
  const origin = window.location.origin
  return slug === 'main' ? `${origin}/menu` : `${origin}/menu/${slug}`
}

/** Resolve menu image path (relative or absolute) for display. */
export function resolveGuestMenuImageUrl(path: string): string {
  const trimmed = (path || '').trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed
  }
  if (trimmed.startsWith('/')) {
    if (typeof window === 'undefined') return trimmed
    return `${window.location.origin}${trimmed}`
  }
  return trimmed
}
