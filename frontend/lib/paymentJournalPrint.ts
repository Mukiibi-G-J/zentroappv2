import { ReceiptReportId } from '@/lib/receiptReportIds'

export const PAYMENT_JOURNAL_PRINT_ACTION = 'print_payment_journal'
export const PAYMENT_JOURNAL_PRINT_HASH = '#print-receipt'

export function isPaymentJournalPrintAction(actionName: string, relativeUrl?: string | null): boolean {
  const url = (relativeUrl || '').trim()
  return actionName === PAYMENT_JOURNAL_PRINT_ACTION || url === PAYMENT_JOURNAL_PRINT_HASH
}

export async function printPaymentJournalReceipt(
  printReport: (reportId: number, body: Record<string, unknown>) => Promise<void>,
  systemId: string,
): Promise<void> {
  await printReport(ReceiptReportId.PAYMENT_JOURNAL, {
    payment_journal_system_id: systemId,
  })
}
