'use client'

import { useCallback, useEffect, useState } from 'react'
import { Eye, Unlink } from 'lucide-react'
import { toast } from 'sonner'
import DynamicDialogModal from '@/components/dynamic/DynamicDialogModal'
import JournalPreviewDialog, {
  type JournalPreviewContent,
} from '@/components/dynamic/JournalPreviewDialog'
import { extractApiErrorMessage } from '@/lib/apiError'
import { formatDisplayDate } from '@/lib/dateFormat'
import { isPreviewActionResponse } from '@/lib/pageActionResponse'
import { pageService } from '@/services/page.service'

export const UNAPPLY_CUSTOMER_ENTRIES_ACTION = '#unapply-customer-entries'
/** CLE list Apply Entries (BC CustEntry-Apply Posted Entries). */
export const APPLY_CUSTOMER_LEDGER_ENTRIES_ACTION = '#apply-customer-ledger-entries'

export interface UnapplyCustomerEntriesContent {
  EntryNo: number
  SystemId: string
  CustomerNo: string
  CustomerName: string
  DocumentNo: string
  PostingDate: string
  DialogTitle?: string
  Lines: Array<{
    EntryNo: number
    PostingDate?: string | null
    EntryType?: string
    DocumentType?: string
    DocumentNo?: string
    CustomerNo?: string | null
    InitialDocumentType?: string | null
    InitialDocumentNo?: string | null
    Amount?: number
    CurrencyCode?: string
  }>
}

interface Props {
  open: boolean
  pageId: number
  systemId: string | null
  onClose: () => void
  onUnapplied?: () => void
}

function formatAmount(value: number | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function UnapplyCustomerEntriesDialog({
  open,
  pageId,
  systemId,
  onClose,
  onUnapplied,
}: Props) {
  const [loading, setLoading] = useState(false)
  const [posting, setPosting] = useState(false)
  const [content, setContent] = useState<UnapplyCustomerEntriesContent | null>(null)
  const [documentNo, setDocumentNo] = useState('')
  const [postingDate, setPostingDate] = useState('')
  const [preview, setPreview] = useState<JournalPreviewContent | null>(null)

  const load = useCallback(async () => {
    if (!open || !systemId) return
    setLoading(true)
    setContent(null)
    try {
      const result = await pageService.invokeAction(
        pageId,
        'load_unapply_customer_entries',
        systemId,
      )
      if (
        typeof result === 'object'
        && result !== null
        && 'Command' in result
        && result.Command === 'OPEN_UNAPPLY'
        && result.Content
      ) {
        const payload = result.Content as UnapplyCustomerEntriesContent
        setContent(payload)
        setDocumentNo(payload.DocumentNo || '')
        setPostingDate((payload.PostingDate || '').slice(0, 10))
        return
      }
      toast.error('Could not load unapply entries')
      onClose()
    } catch (err) {
      toast.error(extractApiErrorMessage(err))
      onClose()
    } finally {
      setLoading(false)
    }
  }, [onClose, open, pageId, systemId])

  useEffect(() => {
    void load()
  }, [load])

  const payload = () => ({
    DocumentNo: documentNo.trim(),
    PostingDate: postingDate,
  })

  const handlePreview = async () => {
    if (!systemId) return
    setPosting(true)
    try {
      const result = await pageService.invokeAction(
        pageId,
        'preview_unapply_customer_entries',
        systemId,
        payload(),
      )
      if (
        isPreviewActionResponse(result)
        && result.Content
        && typeof result.Content === 'object'
        && 'Entries' in result.Content
      ) {
        setPreview(result.Content as JournalPreviewContent)
        return
      }
      toast.error('Preview returned no entries')
    } catch (err) {
      toast.error(extractApiErrorMessage(err))
    } finally {
      setPosting(false)
    }
  }

  const handleUnapply = async () => {
    if (!systemId) return
    if (!documentNo.trim()) {
      toast.error('Document No. is required')
      return
    }
    if (!window.confirm('Do you want to unapply the selected application entries?')) {
      return
    }
    setPosting(true)
    try {
      const result = await pageService.invokeAction(
        pageId,
        'unapply_customer_entries',
        systemId,
        payload(),
      )
      const message =
        (typeof result === 'object'
          && result !== null
          && 'Message' in result
          && typeof result.Message === 'string'
          && result.Message)
        || 'Entries unapplied'
      toast.success(message)
      onUnapplied?.()
      onClose()
    } catch (err) {
      toast.error(extractApiErrorMessage(err))
    } finally {
      setPosting(false)
    }
  }

  if (!open) return null

  const title =
    content?.DialogTitle
    || (content
      ? `Unapply Customer Entries - ${content.CustomerNo} ${content.CustomerName} Entry No. ${content.EntryNo}`
      : 'Unapply Customer Entries')

  return (
    <>
      <DynamicDialogModal open={open} title={title} onClose={onClose} titleId="unapply-customer-entries-title">
        <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
          {loading ? (
            <p className="text-sm text-bodyText">Loading applied entries…</p>
          ) : content ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-bodyText">Document No.</span>
                  <input
                    value={documentNo}
                    onChange={(e) => setDocumentNo(e.target.value)}
                    className="h-9 rounded border border-gray-200 px-2 text-mainTextColor focus:border-s1 focus:outline-none focus:ring-1 focus:ring-s1/30"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-bodyText">Posting Date</span>
                  <input
                    type="date"
                    value={postingDate}
                    onChange={(e) => setPostingDate(e.target.value)}
                    className="h-9 rounded border border-gray-200 px-2 text-mainTextColor focus:border-s1 focus:outline-none focus:ring-1 focus:ring-s1/30"
                  />
                </label>
              </div>

              <div className="flex flex-wrap gap-2 border-b border-gray-100 pb-2">
                <button
                  type="button"
                  disabled={posting}
                  onClick={() => void handleUnapply()}
                  className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1 disabled:opacity-45"
                >
                  <Unlink className="h-4 w-4 text-s1" strokeWidth={1.75} />
                  Unapply
                </button>
                <button
                  type="button"
                  disabled={posting}
                  onClick={() => void handlePreview()}
                  className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1 disabled:opacity-45"
                >
                  <Eye className="h-4 w-4 text-s1" strokeWidth={1.75} />
                  Preview Unapply
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-auto rounded border border-gray-200">
                <table className="min-w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 text-left text-bodyText">
                    <tr>
                      <th className="px-2 py-2 font-medium">Posting Date</th>
                      <th className="px-2 py-2 font-medium">Entry Type</th>
                      <th className="px-2 py-2 font-medium">Document Type</th>
                      <th className="px-2 py-2 font-medium">Document No.</th>
                      <th className="px-2 py-2 font-medium">Customer No.</th>
                      <th className="px-2 py-2 font-medium">Initial Document Type</th>
                      <th className="px-2 py-2 font-medium">Initial Document No.</th>
                      <th className="px-2 py-2 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {content.Lines.map((line) => (
                      <tr key={line.EntryNo} className="hover:bg-[#f7fbfb]">
                        <td className="px-2 py-1.5 whitespace-nowrap">
                          {formatDisplayDate(line.PostingDate)}
                        </td>
                        <td className="px-2 py-1.5">{line.EntryType || '—'}</td>
                        <td className="px-2 py-1.5">{line.DocumentType || '—'}</td>
                        <td className="px-2 py-1.5">{line.DocumentNo || '—'}</td>
                        <td className="px-2 py-1.5">{line.CustomerNo || '—'}</td>
                        <td className="px-2 py-1.5">{line.InitialDocumentType || '—'}</td>
                        <td className="px-2 py-1.5">{line.InitialDocumentNo || '—'}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">
                          {formatAmount(line.Amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded border border-gray-200 bg-white px-3 py-1.5 text-sm text-bodyText hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={posting}
                  onClick={() => void handleUnapply()}
                  className="rounded bg-s1 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-45"
                >
                  OK
                </button>
              </div>
            </>
          ) : null}
        </div>
      </DynamicDialogModal>

      <JournalPreviewDialog
        open={Boolean(preview)}
        preview={preview}
        onClose={() => setPreview(null)}
      />
    </>
  )
}
