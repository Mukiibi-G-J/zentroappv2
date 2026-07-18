import api from '@/lib/api'

export interface ItemImage {
  id: number
  item: string
  url: string
  alt_text?: string | null
}

function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const path = url.startsWith('/') ? url : `/${url}`
  if (typeof window === 'undefined') {
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'
    return `${base}${path}`
  }
  const { hostname } = window.location
  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
  const parts = hostname.split('.')
  const base =
    process.env.NEXT_PUBLIC_API_URL ??
    (parts.length >= 2 ? `http://${hostname}:${port}` : `http://localhost:${port}`)
  return `${base}${path}`
}

export const itemImagesService = {
  resolveUrl: resolveMediaUrl,

  async list(itemNo: string): Promise<ItemImage[]> {
    const res = await api.get<ItemImage[]>('/api/item-images/', {
      params: { item: itemNo },
    })
    const data = res.data
    return Array.isArray(data) ? data : (data as { results?: ItemImage[] }).results ?? []
  },

  async upload(itemNo: string, file: File, altText?: string): Promise<ItemImage> {
    const form = new FormData()
    form.append('item', itemNo)
    form.append('url', file)
    if (altText) form.append('alt_text', altText)
    const res = await api.post<ItemImage>('/api/item-images/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async remove(imageId: number): Promise<void> {
    await api.delete(`/api/item-images/${imageId}/`)
  },
}
