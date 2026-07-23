'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { usePathname, useRouter } from 'next/navigation'
import { ArrowLeft, ExternalLink, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDisplayDate } from '@/lib/dateFormat'
import { usePages } from '@/hooks/usePage'
import { getPageRouteId } from '@/lib/pageRoutes'

interface PreviewEntry {
  Line: number
  Side: string
  LedgerType?: string
  Account: string
  Amount: number
}

export interface PreviewRelatedEntry {
  TableKey: string
  TableName: string
  NoOfEntries: number
  /** BC Navigate Show — open this page-engine list with NavigateFilters. */
  NavigatePageName?: string | null
  NavigateFilters?: Record<string, string> | null
}

export interface AccountHoverInfo {
  No?: string | null
  Name?: string | null
  Balance?: number | null
  Category?: string | null
  Blocked?: boolean
}

export type PreviewDetailRow = Record<string, string | number | boolean | null | undefined | AccountHoverInfo>

export interface JournalPreviewContent {
  Entries: PreviewEntry[]
  RelatedEntries?: PreviewRelatedEntry[]
  EntrySets?: Record<string, PreviewDetailRow[]>
  Message?: string
  BatchName?: string
  DialogTitle?: string
  /** BC Step B title when drilling into a related entry set (e.g. Detailed Customer Ledger Entries Preview). */
  DetailDialogTitle?: string
}

interface Props {
  open: boolean
  preview: JournalPreviewContent | null
  onClose: () => void
}

const ACCOUNT_NO_COLUMNS = new Set([
  'GLAccountNo',
  'VendorNo',
  'CustomerNo',
  'BankAccountNo',
])

function formatHoverBalance(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function parseAccountInfo(raw: unknown): AccountHoverInfo | null {
  if (!raw || typeof raw !== 'object') return null
  const info = raw as AccountHoverInfo
  if (!info.Name && !info.No) return null
  return info
}

function AccountHoverCard({ info, anchorRect }: { info: AccountHoverInfo; anchorRect: DOMRect }) {
  const cardWidth = 320
  const left = Math.min(anchorRect.left, window.innerWidth - cardWidth - 16)
  const top = anchorRect.bottom + 8

  return createPortal(
    <div
      className="fixed z-[70] pointer-events-none"
      style={{ top, left, width: cardWidth }}
      role="tooltip"
    >
      <div className="relative bg-white border border-gray-200 rounded-lg shadow-lg px-4 py-3 text-sm">
        <div className="absolute -top-2 left-6 w-4 h-4 bg-white border-l border-t border-gray-200 rotate-45" />
        <div className="flex items-start justify-between gap-4">
          <span className="text-xs text-bodyText tabular-nums">{info.No ?? '—'}</span>
          {info.Category ? (
            <span className="text-xs text-bodyText text-right">{info.Category}</span>
          ) : null}
        </div>
        {info.Name ? (
          <div className="mt-1 text-base font-semibold text-teal-700 underline decoration-teal-700/40">
            {info.Name}
          </div>
        ) : null}
        <div className="mt-2 flex items-end justify-between gap-4">
          {info.Balance !== null && info.Balance !== undefined ? (
            <span className="text-sm tabular-nums text-mainTextColor">{formatHoverBalance(info.Balance)}</span>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2 text-xs text-bodyText shrink-0">
            <span>Blocked</span>
            <input type="checkbox" checked={Boolean(info.Blocked)} readOnly className="h-3.5 w-3.5" />
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function AccountHoverCell({ value, info }: { value: string; info: AccountHoverInfo | null }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [hovered, setHovered] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)

  if (!info?.Name) {
    return <span>{value}</span>
  }

  return (
    <>
      <span
        ref={ref}
        className="underline decoration-gray-400 underline-offset-2 cursor-default text-mainTextColor"
        onMouseEnter={() => {
          const rect = ref.current?.getBoundingClientRect()
          if (rect) {
            setAnchorRect(rect)
            setHovered(true)
          }
        }}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => {
          const rect = ref.current?.getBoundingClientRect()
          if (rect) {
            setAnchorRect(rect)
            setHovered(true)
          }
        }}
        onBlur={() => setHovered(false)}
        tabIndex={0}
      >
        {value}
      </span>
      {hovered && anchorRect ? <AccountHoverCard info={info} anchorRect={anchorRect} /> : null}
    </>
  )
}

const DETAIL_COLUMNS: Record<string, { key: string; label: string; align?: 'right' }[]> = {
  gl_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'GLAccountNo', label: 'G/L Account No.' },
    { key: 'Description', label: 'Description' },
    { key: 'GenPostingType', label: 'Gen. Posting Type' },
    { key: 'GlobalDimension1', label: 'Global Dimension 1' },
    { key: 'Amount', label: 'Amount', align: 'right' },
  ],
  vendor_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'DocumentDate', label: 'Document Date' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'VendorNo', label: 'Vendor No.' },
    { key: 'VendorName', label: 'Vendor Name' },
    { key: 'Description', label: 'Description' },
    { key: 'Amount', label: 'Amount', align: 'right' },
    { key: 'RemainingAmount', label: 'Remaining Amount', align: 'right' },
  ],
  bank_account_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'BankAccountNo', label: 'Bank Account No.' },
    { key: 'BankAccountName', label: 'Bank Account Name' },
    { key: 'Description', label: 'Description' },
    { key: 'Amount', label: 'Amount', align: 'right' },
  ],
  detailed_vendor_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'EntryType', label: 'Entry Type' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'VendorNo', label: 'Vendor No.' },
    { key: 'Amount', label: 'Amount', align: 'right' },
    { key: 'DebitAmount', label: 'Debit Amount', align: 'right' },
    { key: 'CreditAmount', label: 'Credit Amount', align: 'right' },
  ],
  customer_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'DocumentDate', label: 'Document Date' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'CustomerNo', label: 'Customer No.' },
    { key: 'CustomerName', label: 'Customer Name' },
    { key: 'Description', label: 'Description' },
    { key: 'Amount', label: 'Amount', align: 'right' },
  ],
  detailed_customer_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'EntryType', label: 'Entry Type' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'CustomerNo', label: 'Customer No.' },
    { key: 'CurrencyCode', label: 'Currency Code' },
    { key: 'Amount', label: 'Amount', align: 'right' },
    { key: 'AmountLCY', label: 'Amount (LCY)', align: 'right' },
    { key: 'InitialEntryDueDate', label: 'Initial Entry Due Date' },
  ],
  vat_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'Type', label: 'Type' },
    { key: 'VatBusPostingGroup', label: 'VAT Bus. Posting Group' },
    { key: 'VatProdPostingGroup', label: 'VAT Prod. Posting Group' },
    { key: 'Base', label: 'Base', align: 'right' },
    { key: 'Amount', label: 'Amount', align: 'right' },
    { key: 'VatPercent', label: 'VAT %', align: 'right' },
    { key: 'VatAccountNo', label: 'VAT Account No.' },
  ],
  item_ledger_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'EntryType', label: 'Entry Type' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'ItemNo', label: 'Item No.' },
    { key: 'Description', label: 'Description' },
    { key: 'Quantity', label: 'Quantity', align: 'right' },
    { key: 'LocationCode', label: 'Location Code' },
    { key: 'LotNo', label: 'Lot No.' },
  ],
  value_entry: [
    { key: 'PostingDate', label: 'Posting Date' },
    { key: 'EntryType', label: 'Entry Type' },
    { key: 'DocumentType', label: 'Document Type' },
    { key: 'DocumentNo', label: 'Document No.' },
    { key: 'ItemNo', label: 'Item No.' },
    { key: 'Description', label: 'Description' },
    { key: 'ValuedQuantity', label: 'Valued Quantity', align: 'right' },
    { key: 'CostAmount', label: 'Cost Amount', align: 'right' },
    { key: 'SalesAmount', label: 'Sales Amount', align: 'right' },
  ],
}

function formatCellValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (key.toLowerCase().includes('date')) {
    try {
      return formatDisplayDate(String(value)) || String(value)
    } catch {
      return String(value)
    }
  }
  if (typeof value === 'number') {
    return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return String(value)
}

export default function JournalPreviewDialog({ open, preview, onClose }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const { data: pages = [] } = usePages()
  const [selectedTableKey, setSelectedTableKey] = useState<string | null>(null)
  const [focusedRelatedKey, setFocusedRelatedKey] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setSelectedTableKey(null)
      setFocusedRelatedKey(null)
    }
  }, [open, preview])

  const relatedEntries = useMemo((): PreviewRelatedEntry[] => {
    if (!preview) return []
    if (preview.RelatedEntries?.length) return preview.RelatedEntries
    const counts = new Map<string, number>()
    for (const entry of preview.Entries) {
      const type = entry.LedgerType ?? 'Entry'
      counts.set(type, (counts.get(type) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([tableName, noOfEntries], i) => ({
      TableKey: `legacy_${i}`,
      TableName: tableName,
      NoOfEntries: noOfEntries,
    }))
  }, [preview])

  const navigateToRelatedPage = (row: PreviewRelatedEntry) => {
    const pageName = row.NavigatePageName?.trim()
    if (!pageName) return false
    const target = pages.find((p) => p.Name === pageName)
    if (!target) return false

    const params = new URLSearchParams()
    params.set('page', String(getPageRouteId(target)))
    params.set('return', pathname || '/dashboard')
    params.set('filterLabel', row.TableName)

    const filters = row.NavigateFilters || {}
    for (const [key, value] of Object.entries(filters)) {
      if (value == null || value === '') continue
      params.set(key, String(value))
    }

    const docLabel = filters.document_no || filters.no
    if (docLabel) {
      params.set('ctxLabel', String(docLabel))
    }

    onClose()
    router.push(`/dashboard?${params.toString()}`)
    return true
  }

  const selectedTable = relatedEntries.find((r) => r.TableKey === selectedTableKey)
  const detailRows = selectedTableKey && preview?.EntrySets?.[selectedTableKey]
    ? preview.EntrySets[selectedTableKey]
    : []
  const detailColumns = selectedTableKey ? DETAIL_COLUMNS[selectedTableKey] : undefined
  const focusedRelated = relatedEntries.find((r) => r.TableKey === focusedRelatedKey)
    ?? relatedEntries[0]
    ?? null

  if (!open || !preview) return null

  const showDetail = selectedTableKey && detailColumns && detailRows.length > 0
  const detailTitle =
    preview.DetailDialogTitle
    || (selectedTableKey === 'detailed_customer_ledger_entry'
      ? 'Detailed Customer Ledger Entries Preview'
      : selectedTable?.TableName)
      || 'Entry Preview'

  const openFocusedRelated = () => {
    const row = focusedRelated
    if (!row) return
    if (row.NavigatePageName && navigateToRelatedPage(row)) return
    if (preview.EntrySets?.[row.TableKey]?.length) {
      setSelectedTableKey(row.TableKey)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2 min-w-0">
            {showDetail && (
              <button
                type="button"
                onClick={() => setSelectedTableKey(null)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-bodyText transition shrink-0"
                aria-label="Back to related entries"
              >
                <ArrowLeft size={16} />
              </button>
            )}
            <h2 className="text-base font-semibold text-mainTextColor truncate">
              {showDetail
                ? detailTitle
                : (preview.DialogTitle || 'Posting Preview')}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-bodyText transition shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {!showDetail && relatedEntries.length > 0 ? (
          <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-100">
            <button
              type="button"
              disabled={!focusedRelated}
              onClick={openFocusedRelated}
              className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1 disabled:opacity-45"
            >
              <ExternalLink size={15} className="text-s1 shrink-0" strokeWidth={1.75} />
              <span>Show Related Entries</span>
            </button>
          </div>
        ) : null}

        {preview.BatchName && !showDetail && (
          <div className="px-5 py-2 bg-gray-50 border-b border-gray-200 text-sm text-bodyText">
            Batch: <span className="font-medium text-mainTextColor">{preview.BatchName}</span>
          </div>
        )}

        <div className="overflow-auto flex-1 p-5">
          {preview.Message && !showDetail && (
            <p className="mb-4 text-sm text-bodyText">{preview.Message}</p>
          )}

          {!showDetail ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs font-medium text-bodyText uppercase tracking-wide">
                  <th className="px-4 py-2.5 text-left">Related Entries</th>
                  <th className="px-4 py-2.5 text-right w-36">No. of Entries</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {relatedEntries.map((row) => {
                  const canNavigate = Boolean(
                    row.NavigatePageName
                    && pages.some((p) => p.Name === row.NavigatePageName),
                  )
                  const hasDetail = Boolean(preview.EntrySets?.[row.TableKey]?.length)
                  const clickable = canNavigate || hasDetail
                  const focused = focusedRelated?.TableKey === row.TableKey
                  return (
                    <tr
                      key={row.TableKey}
                      className={cn(
                        'transition',
                        clickable ? 'cursor-pointer hover:bg-s1/5' : 'hover:bg-gray-50',
                        focused && 'bg-[#eef6f7]',
                      )}
                      title={
                        canNavigate
                          ? `Open ${row.TableName} filtered to this document`
                          : hasDetail
                            ? `Show ${row.TableName} preview`
                            : undefined
                      }
                      onClick={() => {
                        setFocusedRelatedKey(row.TableKey)
                        if (canNavigate && navigateToRelatedPage(row)) return
                        if (hasDetail) setSelectedTableKey(row.TableKey)
                      }}
                    >
                      <td className="px-4 py-3 text-mainTextColor font-medium">
                        <span className="inline-flex items-center gap-2">
                          {row.TableName}
                          {canNavigate ? (
                            <ExternalLink size={13} className="text-s1 shrink-0" />
                          ) : null}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-mainTextColor">
                        {row.NoOfEntries}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-sm min-w-max">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs font-medium text-bodyText uppercase tracking-wide">
                  {detailColumns!.map((col) => (
                    <th
                      key={col.key}
                      className={cn(
                        'px-3 py-2 whitespace-nowrap',
                        col.align === 'right' ? 'text-right' : 'text-left',
                      )}
                    >
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {detailRows.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    {detailColumns!.map((col) => {
                      const raw = row[col.key]
                      const isAmount = col.key.toLowerCase().includes('amount')
                      const num = typeof raw === 'number' ? raw : Number(raw)
                      const accountInfo =
                        ACCOUNT_NO_COLUMNS.has(col.key) ? parseAccountInfo(row.AccountInfo) : null
                      const displayValue = formatCellValue(col.key, raw)
                      return (
                        <td
                          key={col.key}
                          className={cn(
                            'px-3 py-2 whitespace-nowrap',
                            col.align === 'right' ? 'text-right tabular-nums' : 'text-left',
                            isAmount && num < 0 ? 'text-red-600' : 'text-mainTextColor',
                          )}
                        >
                          {accountInfo ? (
                            <AccountHoverCell value={displayValue} info={accountInfo} />
                          ) : (
                            displayValue
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="px-5 py-3 border-t border-gray-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
