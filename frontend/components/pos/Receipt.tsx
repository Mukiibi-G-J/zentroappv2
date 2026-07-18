'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { toast } from 'sonner'
import { THERMAL_BROWSER_RECEIPT_PRINT_CSS } from '@/lib/thermalBrowserReceiptPrintCss'
import {
  ZENTRO_THERMAL_PRINT_CHROME_CLASS,
  ZENTRO_THERMAL_PRINT_DIALOG_CLASS,
  ZENTRO_THERMAL_PRINT_OVERLAY_CLASS,
} from '@/lib/zentroPrintClassNames'
import {
  ensureZentroPrintHideRootBeforePrint,
  useZentroPrintHideRootWhileOpen,
} from '@/hooks/useZentroPrintHideRoot'

/** Strip noisy suffixes from payment method labels (e.g. "Cash Cust." → "Cash") */
function cleanPaymentMethodLabel(desc?: string): string {
  if (!desc) return ''
  return desc.replace(/\s+cust\.?$/i, '').trim()
}

export interface ReceiptInvoice {
  invoice_no: string
  customer_name: string
  customer_no?: string
  total_amount: number | string
  amount_received?: number
  change_amount?: number
  document_date: string
  total_excl_vat?: number
  vat_amount?: number
  vat_enabled?: boolean
  created_at: string
  receipt_variant?: 'sale' | 'prepayment'
  prepayment_document_no?: string
  transaction_no?: string
  remaining_balance?: number | string
  payment_method?: {
    id: number
    name: string
    code: string
  }
  payment_method_details?: {
    id: number
    code: string
    description: string
    requires_amount_received: boolean
  }
  lines: Array<{
    item_name: string
    quantity: number | string
    unit_price: number | string
    total_price?: number | string
    total_amount?: number | string
    unit_of_measure?: string
    quantity_per_unit?: number
    original_price?: number | string
  }>
}

export interface ReceiptBusinessInfo {
  name: string
  displayName?: string
  branchCode?: string
  logo?: string
  address: string
  phone: string
  email: string
  website?: string
  tin: string
  vatNo: string
}

export interface ReceiptSellerInfo {
  name: string
  email?: string
}

interface ReceiptProps {
  invoice: ReceiptInvoice
  businessInfo: ReceiptBusinessInfo
  sellerInfo: ReceiptSellerInfo
  isOpen: boolean
  onClose: () => void
}

export function Receipt({ invoice, businessInfo, sellerInfo, isOpen, onClose }: ReceiptProps) {
  const [mounted, setMounted] = useState(false)
  const [isPrinting, setIsPrinting] = useState(false)
  const [printMethod, setPrintMethod] = useState<'browser' | 'printer'>('browser')

  useEffect(() => setMounted(true), [])
  useZentroPrintHideRootWhileOpen(isOpen && !!invoice)

  const safeBusinessAddress = (() => {
    const addr = String(businessInfo.address ?? '').trim()
    if (!addr) return ''
    if (businessInfo.branchCode) {
      const hasDigits = /\d/.test(addr)
      const hasPunctuation = /[,/#-]/.test(addr)
      const wordCount = addr.split(/\s+/).filter(Boolean).length
      const isSingleWord = wordCount <= 1
      const isShort = addr.length <= 24
      if (isSingleWord && isShort && !hasDigits && !hasPunctuation) {
        return ''
      }
    }
    return addr
  })()

  const handleBrowserPrint = () => {
    ensureZentroPrintHideRootBeforePrint()
    window.print()
  }

  const handleDirectPrint = async () => {
    if (!('serial' in navigator)) {
      toast.error('Web Serial API not supported. Please use Chrome, Edge, or Opera browser.')
      return
    }

    setIsPrinting(true)
    try {
      toast.error('Direct printer is not configured yet. Please use browser print.')
    } finally {
      setIsPrinting(false)
    }
  }

  const handlePrint = () => {
    if (printMethod === 'browser') {
      handleBrowserPrint()
    } else {
      void handleDirectPrint()
    }
  }

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      if (Number.isNaN(date.getTime())) {
        return 'Invalid Date'
      }
      const formatted = date.toLocaleString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'Africa/Kampala',
      })
      return formatted.replace(',', '').trim()
    } catch {
      const now = new Date()
      return now
        .toLocaleString('en-GB', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
          timeZone: 'Africa/Kampala',
        })
        .replace(',', '')
        .trim()
    }
  }

  const formatNumber = (num: number | string | undefined | null): string => {
    if (num === undefined || num === null) return '0'
    const numericValue = typeof num === 'string' ? parseFloat(num) : num
    if (Number.isNaN(numericValue)) return '0'
    return Math.round(numericValue).toLocaleString('en-US')
  }

  const parseNumber = (num: number | string | undefined | null): number => {
    if (num === undefined || num === null) return 0
    const numericValue = typeof num === 'string' ? parseFloat(num) : num
    return Number.isNaN(numericValue) ? 0 : numericValue
  }

  if (!mounted || !isOpen || !invoice) return null

  const isPrepayment = invoice.receipt_variant === 'prepayment'

  const safeInvoice = {
    invoice_no: invoice.invoice_no || 'N/A',
    customer_name: invoice.customer_name || 'N/A',
    customer_no: invoice.customer_no,
    total_amount: parseNumber(invoice.total_amount),
    amount_received:
      parseNumber(invoice.amount_received) || parseNumber(invoice.total_amount),
    change_amount: parseNumber(invoice.change_amount) || 0,
    document_date:
      invoice.document_date || invoice.created_at || new Date().toISOString(),
    created_at: invoice.created_at || new Date().toISOString(),
    lines: invoice.lines || [],
  }

  if (
    safeInvoice.change_amount === 0 &&
    safeInvoice.amount_received > safeInvoice.total_amount
  ) {
    safeInvoice.change_amount = safeInvoice.amount_received - safeInvoice.total_amount
  }

  const modal = (
    <div
      className={`${ZENTRO_THERMAL_PRINT_OVERLAY_CLASS} fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4`}
    >
      <div
        className={`${ZENTRO_THERMAL_PRINT_DIALOG_CLASS} max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg bg-white shadow-xl`}
      >
        <div className={`${ZENTRO_THERMAL_PRINT_CHROME_CLASS} border-b p-4`}>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">
              {isPrepayment ? 'Payment receipt' : 'Receipt'}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded bg-gray-600 px-3 py-1 text-sm text-white hover:bg-gray-700"
            >
              Close
            </button>
          </div>

          <div className="mt-3 flex flex-col gap-2">
            <div className="flex gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="printMethod"
                  value="browser"
                  checked={printMethod === 'browser'}
                  onChange={() => setPrintMethod('browser')}
                  className="h-4 w-4"
                />
                <span>Browser Print</span>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="printMethod"
                  value="printer"
                  checked={printMethod === 'printer'}
                  onChange={() => setPrintMethod('printer')}
                  className="h-4 w-4"
                  disabled={!('serial' in navigator)}
                />
                <span>
                  Direct Printer
                  {!('serial' in navigator) && (
                    <span className="ml-1 text-xs text-gray-500">(Not supported)</span>
                  )}
                </span>
              </label>
            </div>
            <button
              type="button"
              onClick={handlePrint}
              disabled={isPrinting}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
            >
              {isPrinting ? 'Printing...' : 'Print'}
            </button>
          </div>
        </div>

        <div className="flex justify-center p-0 print:p-0">
          <div className="receipt-container mx-auto w-full max-w-[48mm] bg-white text-sm text-black print:max-w-[48mm]">
            <div className="mb-1 text-center">
              {businessInfo.logo ? (
                <div className="mb-0.5">
                  <img
                    src={businessInfo.logo}
                    alt="Company Logo"
                    className="mx-auto h-8 w-auto"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none'
                    }}
                  />
                </div>
              ) : null}
              <div className="receipt-print-title mb-0.5 break-words text-lg font-bold">
                {isPrepayment ? 'PAYMENT RECEIPT' : 'SALES RECEIPT'}
              </div>
              <div className="mb-0.5 break-words text-[10px] font-bold">
                {businessInfo.displayName || businessInfo.name}
              </div>
              {businessInfo.branchCode
                ? (() => {
                    const branch = String(businessInfo.branchCode).split(/\r?\n/)[0].trim()
                    const companyName = String(
                      businessInfo.displayName || businessInfo.name || '',
                    ).trim()
                    if (!branch || branch.toLowerCase() === companyName.toLowerCase()) {
                      return null
                    }
                    return (
                      <div className="text-primary mb-0.5 break-words text-[9px] font-medium">
                        {branch}
                      </div>
                    )
                  })()
                : null}
              {safeBusinessAddress ? (
                <div className="mb-0.5 break-words text-[9px]">{safeBusinessAddress}</div>
              ) : null}
              <div className="mb-0.5 break-words text-[9px]">Tel: {businessInfo.phone}</div>
              {businessInfo.email ? (
                <div className="mb-0.5 truncate break-words text-[9px]">{businessInfo.email}</div>
              ) : null}
              {businessInfo.tin ? (
                <div className="mb-0.5 break-words text-[9px]">TIN: {businessInfo.tin}</div>
              ) : null}
              {businessInfo.vatNo ? (
                <div className="mb-1 break-words text-[9px]">VAT No: {businessInfo.vatNo}</div>
              ) : null}
            </div>

            <div className="mb-1 border-t border-dashed border-gray-400" />

            {safeInvoice.customer_name ? (
              <div className="mb-0.5">
                <div className="break-words text-[9px]">
                  Customer: {safeInvoice.customer_name}
                </div>
                {invoice.customer_no ? (
                  <div className="break-words text-[9px]">Account: {invoice.customer_no}</div>
                ) : null}
                {isPrepayment &&
                safeInvoice.invoice_no &&
                safeInvoice.invoice_no !== 'N/A' ? (
                  <div className="break-words text-[9px] font-semibold">
                    This payment #: {safeInvoice.invoice_no}
                  </div>
                ) : null}
                {isPrepayment && invoice.prepayment_document_no ? (
                  <div className="break-words text-[9px]">
                    Order #: {invoice.prepayment_document_no}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="mb-1">
              <table className="w-full border-collapse text-[10px]">
                <thead>
                  <tr className="border-b border-gray-300">
                    <th className="whitespace-nowrap text-center" style={{ width: '10%' }}>
                      Qty
                    </th>
                    <th className="pl-2 text-left">Item Name</th>
                    <th
                      className="receipt-print-price-heading whitespace-nowrap text-right"
                      style={{ width: '28%' }}
                    >
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {safeInvoice.lines.map((line, index) => {
                    const lineTotal = parseNumber(line.total_price || line.total_amount || 0)
                    const safeLine = {
                      item_name: line.item_name || 'Unknown Item',
                      quantity: parseNumber(line.quantity),
                      total_price: lineTotal,
                      unit_of_measure: line.unit_of_measure ?? 'PCS',
                    }

                    return (
                      <tr key={index} className="border-b border-dashed border-gray-200">
                        <td className="whitespace-nowrap text-center text-[9px] tabular-nums">
                          {safeLine.quantity}x
                        </td>
                        <td className="break-words pl-2 pr-1 text-left text-[9px]">
                          {safeLine.item_name}
                          {safeLine.unit_of_measure &&
                          String(safeLine.unit_of_measure).toUpperCase() !== 'PCS' ? (
                            <span className="ml-1 text-[9px] text-gray-600">
                              ({safeLine.unit_of_measure})
                            </span>
                          ) : null}
                        </td>
                        <td className="receipt-print-line-price pr-4 text-right text-[9px] tabular-nums">
                          {formatNumber(safeLine.total_price)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="mb-1 border-t border-dashed border-gray-400" />

            <div className="summary-section mb-1">
              {!isPrepayment ? (
                <div className="mb-0.5 text-center">
                  <div className="text-[10px] font-bold">
                    {`${safeInvoice.lines.length} item${safeInvoice.lines.length === 1 ? '' : 's'} sold`}
                  </div>
                </div>
              ) : null}

              {!isPrepayment &&
              invoice.vat_enabled &&
              invoice.vat_amount != null &&
              parseNumber(invoice.vat_amount) > 0 ? (
                <>
                  <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                    <span className="text-left">Subtotal (excl. VAT):</span>
                    <span className="receipt-print-summary-num pr-4 text-right tabular-nums">
                      {formatNumber(
                        invoice.total_excl_vat ??
                          parseNumber(safeInvoice.total_amount) -
                            parseNumber(invoice.vat_amount),
                      )}
                    </span>
                  </div>
                  <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                    <span className="text-left">VAT Amount:</span>
                    <span className="receipt-print-summary-num pr-4 text-right tabular-nums">
                      {formatNumber(invoice.vat_amount)}
                    </span>
                  </div>
                </>
              ) : null}

              <div className="mb-0.5 grid grid-cols-2 gap-0.5">
                <span className="receipt-print-total-label text-left text-[12px] font-bold">
                  {isPrepayment ? 'Total for this order:' : 'Total:'}
                </span>
                <span className="receipt-print-total-num pr-4 text-right text-[12px] font-bold tabular-nums">
                  {formatNumber(safeInvoice.total_amount)}
                </span>
              </div>

              {invoice.payment_method_details &&
              invoice.payment_method_details.code !== 'NOT_PAID' ? (
                isPrepayment ? (
                  <>
                    <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                      <span className="text-left font-bold">Paid today:</span>
                      <span className="receipt-print-summary-num pr-4 text-right font-bold tabular-nums">
                        {formatNumber(safeInvoice.amount_received)}
                      </span>
                    </div>
                    {invoice.remaining_balance != null ? (
                      <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                        <span className="text-left font-bold">Still to pay:</span>
                        <span className="receipt-print-summary-num pr-4 text-right font-bold tabular-nums">
                          {formatNumber(invoice.remaining_balance)}
                        </span>
                      </div>
                    ) : null}
                    <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                      <span className="text-left">Paid with:</span>
                      <span className="receipt-print-summary-num pr-4 text-right">
                        {cleanPaymentMethodLabel(invoice.payment_method_details.description)}
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                      <span className="text-left font-bold">Tendered Total:</span>
                      <span className="receipt-print-summary-num pr-4 text-right font-bold tabular-nums">
                        {formatNumber(safeInvoice.amount_received)}
                      </span>
                    </div>
                    <div className="mb-0.5 grid grid-cols-2 gap-0.5 text-[9px]">
                      <span className="text-left font-bold">Change:</span>
                      <span className="receipt-print-summary-num pr-4 text-right font-bold tabular-nums">
                        {formatNumber(safeInvoice.change_amount)}
                      </span>
                    </div>
                  </>
                )
              ) : null}
            </div>

            <div className="mb-1 border-t border-dashed border-gray-400" />

            <div className="mb-1 text-center">
              <div className="text-[10px] font-bold">THANK YOU</div>
            </div>

            <div className="mb-0.5 text-center text-[9px]">
              <div className="grid grid-cols-4 gap-0.5">
                <div className="truncate text-center">{safeInvoice.invoice_no}</div>
                <div className="truncate text-center">
                  {(() => {
                    const dateTime = safeInvoice.created_at || safeInvoice.document_date
                    const dateStr = formatDate(dateTime)
                    return dateStr.split(' ')[0] || ''
                  })()}
                </div>
                <div className="truncate text-center">
                  {(() => {
                    const dateTime = safeInvoice.created_at || safeInvoice.document_date
                    const dateStr = formatDate(dateTime)
                    return dateStr.split(' ').slice(1).join(' ') || ''
                  })()}
                </div>
                <div className="truncate text-center">{sellerInfo.name}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{THERMAL_BROWSER_RECEIPT_PRINT_CSS}</style>
    </div>
  )

  return createPortal(modal, document.body)
}
