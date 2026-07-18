import { ReceiptReportId } from '@/lib/receiptReportIds'
import { normalizeReportPayload, receiptReportService } from '@/services/receiptReport.service'
import { buildAndCompileBrowserHtml } from '@/shared/receipt/receiptBrowserRuntime'

function openPrintHtml(html: string) {
  const printWindow = window.open('', '_blank', 'width=400,height=720')
  if (!printWindow) return false
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => {
    try {
      printWindow.print()
      printWindow.close()
    } catch {
      /* ignore */
    }
  }, 400)
  return true
}

/** After Send: print KOT and/or bar tickets using report templates. */
export async function printFireTickets(
  orderId: number,
  kitchenTicket?: Record<string, unknown> | null,
  barTicket?: Record<string, unknown> | null,
): Promise<void> {
  const printTicket = async (reportId: number, ticket: Record<string, unknown>) => {
    const result = await receiptReportService.runReport(reportId, {
      order_id: orderId,
      device_type: 'web',
      printer_type: 'browser',
    })
    const receiptType =
      ticket.receiptType ??
      (reportId === ReceiptReportId.BAR_ORDER ? 'bar' : 'kot')
    const payload = normalizeReportPayload({ ...ticket, receiptType })
    const html = buildAndCompileBrowserHtml(payload, result.template, result.branding)
    openPrintHtml(html)
  }

  if (kitchenTicket && Array.isArray(kitchenTicket.items) && kitchenTicket.items.length > 0) {
    await printTicket(ReceiptReportId.KITCHEN_ORDER, kitchenTicket)
  } else if (
    kitchenTicket &&
    Array.isArray(kitchenTicket.lines) &&
    kitchenTicket.lines.length > 0
  ) {
    await printTicket(ReceiptReportId.KITCHEN_ORDER, {
      ...kitchenTicket,
      receiptType: 'kot',
      items: kitchenTicket.lines,
    })
  }
  if (barTicket && Array.isArray(barTicket.items) && barTicket.items.length > 0) {
    await printTicket(ReceiptReportId.BAR_ORDER, barTicket)
  }
}
