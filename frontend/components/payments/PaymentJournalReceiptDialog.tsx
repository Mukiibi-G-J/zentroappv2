'use client'

import { useEffect, useState } from 'react'
import { Loader2, Printer, X } from 'lucide-react'
import { buildAndCompileBrowserHtml } from '@/shared/receipt/receiptBrowserRuntime'
import { THERMAL_BROWSER_RECEIPT_PRINT_CSS } from '@/lib/thermalBrowserReceiptPrintCss'
import { ReceiptReportId } from '@/lib/receiptReportIds'
import {
  normalizeReportPayload,
  receiptReportService,
} from '@/services/receiptReport.service'
import { ensureZentroPrintHideRootBeforePrint } from '@/hooks/useZentroPrintHideRoot'

interface Props {
  open: boolean
  systemId: string | null
  onClose: () => void
}

function openPrintHtml(html: string) {
  const printWindow = window.open('', '_blank', 'width=400,height=720')
  if (!printWindow) {
    throw new Error('Pop-up blocked — allow pop-ups to print receipts')
  }
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => {
    try {
      printWindow.print()
      printWindow.close()
    } catch {
      /* window may already be closed */
    }
  }, 400)
}

export function PaymentJournalReceiptDialog({ open, systemId, onClose }: Props) {
  const [html, setHtml] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [printing, setPrinting] = useState(false)

  useEffect(() => {
    if (!open || !systemId) {
      setHtml(null)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    receiptReportService
      .runReport(ReceiptReportId.PAYMENT_JOURNAL, {
        payment_journal_system_id: systemId,
        device_type: 'web',
        printer_type: 'browser',
      })
      .then((result) => {
        if (cancelled) return
        const payload = normalizeReportPayload(result.payload)
        const compiled = buildAndCompileBrowserHtml(payload, result.template, result.branding)
        setHtml(compiled)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load payment receipt')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [open, systemId])

  if (!open) return null

  const handlePrint = () => {
    if (!html) return
    setPrinting(true)
    try {
      ensureZentroPrintHideRootBeforePrint()
      openPrintHtml(html)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Print failed')
    } finally {
      setPrinting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-70 flex items-end justify-center bg-black/45 p-4 sm:items-center">
      <div className="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <h2 className="text-lg font-semibold text-mainTextColor">Payment receipt</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-bodyText hover:bg-softBg hover:text-mainTextColor"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-[200px] flex-1 overflow-y-auto bg-gray-50 p-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-bodyText">
              <Loader2 size={18} className="animate-spin text-primaryColor" />
              Preparing receipt…
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-800">
              {error}
              <p className="mt-2 text-xs text-red-700">
                Run{' '}
                <code className="rounded bg-red-100 px-1">
                  python manage.py seed_receipt_templates --tenant primewise
                </code>{' '}
                if templates are missing.
              </p>
            </div>
          ) : html ? (
            <div className="mx-auto w-full max-w-[48mm] rounded-lg border border-strokeColor bg-white p-2 shadow-sm">
              <iframe
                title="Payment receipt preview"
                srcDoc={`<!DOCTYPE html><html><head><style>${THERMAL_BROWSER_RECEIPT_PRINT_CSS}</style></head><body>${html}</body></html>`}
                className="h-[420px] w-full border-0 bg-white"
              />
            </div>
          ) : null}
        </div>

        <div className="flex gap-2 border-t border-strokeColor p-4">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-strokeColor px-4 py-2.5 text-sm font-medium text-bodyText hover:bg-softBg"
          >
            Close
          </button>
          <button
            type="button"
            disabled={!html || printing}
            onClick={handlePrint}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-s1 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {printing ? <Loader2 size={16} className="animate-spin" /> : <Printer size={16} />}
            Print
          </button>
        </div>
      </div>
    </div>
  )
}
