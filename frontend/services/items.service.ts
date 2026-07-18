import api from '@/lib/api'
import type { ItemTrackingCode, POSTrackingOption } from '@/types/pos'

export interface ItemDetail {
  no: string
  system_id: string
  item_name: string
  type?: string
  unit_price: number
  inventory?: number
  unit_of_measure?: string
  tracking_code?: ItemTrackingCode | null
}

export type ItemImportMode = 'standard' | 'opening_balance'
export type ItemExportFormat = 'excel' | 'pdf'

export type ItemImportStatus = {
  task_id: string
  status: string
  message: string
  progress?: number
  created_count?: number
  updated_count?: number
  failed_count?: number
  total_rows?: number
  errors?: string[]
  error?: string
  journals_created?: number
  journal_document_nos?: string[]
  warnings?: string[]
}

interface ItemLedgerApiEntry {
  lot_no?: string | null
  document_no?: string | null
  remaining_quantity?: number | null
  expiry_date?: string | null
  entry_type?: string | null
  document_type?: string | null
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function searchItems(query: string, limit = 20): Promise<ItemDetail[]> {
  const q = query.trim()
  if (!q) return []
  const res = await api.get<{ results?: ItemDetail[] }>('/api/items/', {
    params: { search: q, page_size: limit },
  })
  return res.data.results ?? []
}

export async function getItemByNo(no: string): Promise<ItemDetail | null> {
  const res = await api.get<{ results?: ItemDetail[] }>('/api/items/', {
    params: { no },
  })
  return res.data.results?.[0] ?? null
}

export async function downloadItemImportTemplate(
  importMode: ItemImportMode = 'standard',
): Promise<void> {
  const res = await api.get<Blob>('/api/items/import_template/', {
    params: { import_mode: importMode },
    responseType: 'blob',
  })
  const filename =
    importMode === 'opening_balance'
      ? 'item_import_template_opening_balance.xlsx'
      : 'item_import_template.xlsx'
  triggerBlobDownload(res.data, filename)
}

export async function startItemImport(
  file: File,
  importMode: ItemImportMode = 'standard',
): Promise<{ task_id: string; message: string; status: string }> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('import_mode', importMode)
  const res = await api.post<{ task_id: string; message: string; status: string }>(
    '/api/items/import_items/',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data
}

export async function checkItemImportStatus(taskId: string): Promise<ItemImportStatus> {
  const res = await api.get<ItemImportStatus>('/api/items/import_items_status/', {
    params: { task_id: taskId },
  })
  return res.data
}

export async function startItemExport(
  format: ItemExportFormat,
  filters: Record<string, unknown> = {},
): Promise<{ task_id: string; message: string; status: string }> {
  const res = await api.post<{ task_id: string; message: string; status: string }>(
    '/api/items/export/',
    { format, filters, item_ids: null },
  )
  return res.data
}

export async function pollItemExportDownload(
  taskId: string,
  format: ItemExportFormat,
  onProgress?: (message: string) => void,
): Promise<void> {
  const maxAttempts = 90
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const res = await api.get<ArrayBuffer>('/api/items/export_status/', {
      params: { task_id: taskId },
      responseType: 'arraybuffer',
    })

    const contentType = String(res.headers?.['content-type'] || '')
    const isFile =
      contentType.includes('application/vnd.openxmlformats')
      || contentType.includes('application/pdf')
      || contentType.includes('application/octet-stream')

    if (isFile) {
      const mimeType =
        format === 'excel'
          ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          : 'application/pdf'
      const blob = new Blob([res.data], { type: mimeType })
      if (blob.size === 0) throw new Error('Downloaded file is empty')
      const ext = format === 'excel' ? 'xlsx' : 'pdf'
      const date = new Date().toISOString().split('T')[0]
      triggerBlobDownload(blob, `items_export_${date}.${ext}`)
      return
    }

    let statusPayload: { status?: string; message?: string; error?: string } = {}
    try {
      const text = new TextDecoder().decode(res.data)
      statusPayload = JSON.parse(text) as typeof statusPayload
    } catch {
      statusPayload = {}
    }

    if (statusPayload.status === 'failure') {
      throw new Error(statusPayload.error || statusPayload.message || 'Export failed')
    }

    onProgress?.(statusPayload.message || `Preparing ${format.toUpperCase()} file…`)
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  throw new Error('Export is taking longer than expected. Please try again.')
}

export async function fetchAllItemLedgerEntries(itemNo: string): Promise<ItemLedgerApiEntry[]> {
  let allEntries: ItemLedgerApiEntry[] = []
  let page = 1
  const pageSize = 500
  let totalCount = 0
  let hasMore = true

  while (hasMore) {
    const res = await api.get<{
      results?: ItemLedgerApiEntry[]
      ledger_entries?: ItemLedgerApiEntry[]
      count?: number
      next?: string | null
    }>(`/api/item-ledger/${encodeURIComponent(itemNo)}/`, {
      params: { page, page_size: pageSize },
    })
    const pageEntries = res.data.results ?? res.data.ledger_entries ?? []
    allEntries = [...allEntries, ...pageEntries]

    if (page === 1 && res.data.count != null) {
      totalCount = res.data.count
    }

    const hasNextUrl = res.data.next != null
    const gotFullPage = pageEntries.length === pageSize
    const hasMoreEntries = totalCount > 0 ? allEntries.length < totalCount : gotFullPage
    hasMore = hasNextUrl || (gotFullPage && hasMoreEntries)
    page += 1

    if (page > 50) break
  }

  return allEntries
}

export function pickAvailableLots(entries: ItemLedgerApiEntry[]): POSTrackingOption[] {
  const validEntries = entries
    .filter((entry) => {
      const hasLotNo = Boolean(entry.lot_no?.trim())
      const hasRemainingQty = (entry.remaining_quantity ?? 0) > 0
      const isSalesEntry =
        (entry.document_no && entry.document_no.startsWith('SIN-')) ||
        entry.entry_type === 'Sale' ||
        entry.document_type === 'Sales'
      return hasLotNo && hasRemainingQty && !isSalesEntry
    })
    .map((entry) => ({
      lot_no: entry.lot_no!,
      document_no: entry.document_no ?? '',
      remaining_quantity: entry.remaining_quantity ?? 0,
      expiry_date: entry.expiry_date ?? null,
      entry_type: entry.entry_type ?? '',
    }))

  const sortedEntries = validEntries.sort((a, b) => {
    const dateA = new Date(a.expiry_date || '9999-12-31')
    const dateB = new Date(b.expiry_date || '9999-12-31')
    if (dateA.getTime() !== dateB.getTime()) {
      return dateA.getTime() - dateB.getTime()
    }
    return a.lot_no.localeCompare(b.lot_no)
  })

  const fifoEntries: POSTrackingOption[] = []
  const usedLots = new Set<string>()

  for (const entry of sortedEntries) {
    if (!usedLots.has(entry.lot_no)) {
      fifoEntries.push(entry)
      usedLots.add(entry.lot_no)
    } else {
      const existingEntry = fifoEntries.find((e) => e.lot_no === entry.lot_no)
      if (existingEntry) {
        const existingDate = new Date(existingEntry.expiry_date || '9999-12-31')
        const currentDate = new Date(entry.expiry_date || '9999-12-31')
        if (currentDate < existingDate) {
          const index = fifoEntries.findIndex((e) => e.lot_no === entry.lot_no)
          fifoEntries[index] = entry
        }
      }
    }
  }

  return fifoEntries
}

export function itemRequiresTracking(tracking?: ItemTrackingCode | null): boolean {
  if (!tracking) return false
  return Boolean(
    tracking.require_lot_no || tracking.require_serial_no || tracking.require_expiry_date,
  )
}
