'use client'

import { useCallback, useState } from 'react'
import { buildAndCompileBrowserHtml } from '@/shared/receipt/receiptBrowserRuntime'
import { ensureZentroPrintHideRootBeforePrint } from '@/hooks/useZentroPrintHideRoot'
import {
  normalizeReportPayload,
  receiptReportService,
} from '@/services/receiptReport.service'

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

export function useReceiptReportPrint() {
  const [printing, setPrinting] = useState(false)

  const printReport = useCallback(async (reportId: number, body: Record<string, unknown>) => {
    setPrinting(true)
    try {
      const result = await receiptReportService.runReport(reportId, {
        device_type: 'web',
        printer_type: 'browser',
        ...body,
      })
      const payload = normalizeReportPayload(result.payload)
      const html = buildAndCompileBrowserHtml(payload, result.template, result.branding)
      ensureZentroPrintHideRootBeforePrint()
      openPrintHtml(html)
    } finally {
      setPrinting(false)
    }
  }, [])

  const printFromPayload = useCallback(
    async (
      payload: Record<string, unknown>,
      template: Parameters<typeof buildAndCompileBrowserHtml>[1],
      branding: Parameters<typeof buildAndCompileBrowserHtml>[2],
    ) => {
      const html = buildAndCompileBrowserHtml(
        normalizeReportPayload(payload),
        template,
        branding,
      )
      ensureZentroPrintHideRootBeforePrint()
      openPrintHtml(html)
    },
    [],
  )

  return { printReport, printFromPayload, printing }
}
