import api from '@/lib/api'

export interface DocumentAttachment {
  id: number
  purchase_invoice: number
  name: string
  display_name: string
  file_url: string | null
  created_at: string
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

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  if (dot < 0 || dot === name.length - 1) return ''
  return name.slice(dot + 1).toUpperCase()
}

export const documentAttachmentsService = {
  resolveUrl: resolveMediaUrl,

  async list(purchaseInvoiceId: string): Promise<DocumentAttachment[]> {
    const res = await api.get<DocumentAttachment[]>('/api/document-attachments/', {
      params: { purchase_invoice: purchaseInvoiceId },
    })
    const data = res.data
    return Array.isArray(data) ? data : (data as { results?: DocumentAttachment[] }).results ?? []
  },

  async upload(purchaseInvoiceId: string, file: File, name?: string): Promise<DocumentAttachment> {
    const form = new FormData()
    form.append('purchase_invoice', purchaseInvoiceId)
    form.append('file', file)
    if (name) form.append('name', name)
    const res = await api.post<DocumentAttachment>('/api/document-attachments/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async remove(attachmentId: number): Promise<void> {
    await api.delete(`/api/document-attachments/${attachmentId}/`)
  },

  async download(attachmentId: number, filename: string): Promise<void> {
    const res = await api.get<Blob>(`/api/document-attachments/${attachmentId}/download/`, {
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
}
