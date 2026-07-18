'use client'

import { useEffect, useState } from 'react'
import { formatAmountInput, formatDecimalDisplay, parseNumericInput } from '@/lib/formatNumber'
import { ReceiptReportId } from '@/lib/receiptReportIds'
import { useReceiptReportPrint } from '@/hooks/useReceiptReportPrint'
import { salesService } from '@/services/sales.service'
import { restaurantService } from '@/services/restaurant.service'
import type { POSCustomer, POSPaymentMethod } from '@/types/pos'
import { toast } from 'sonner'

interface Props {
  open: boolean
  orderId: number
  total: number
  mode?: 'counter' | 'dine_in'
  initialCustomerId?: number | null
  combineOrdersAvailable?: boolean
  /** Settle one split segment only (`main` or check id). Omit / null = whole unpaid balance. */
  checkId?: number | 'main' | null
  onClose: () => void
  onSuccess: (result?: { orderCompleted: boolean }) => void
}

function pickDefaultCustomerId(
  list: POSCustomer[],
  preferredId?: number | null,
): number | null {
  if (preferredId && list.some((c) => c.id === preferredId)) {
    return preferredId
  }
  const walkIn =
    list.find((c) => /general|walk-?in|cash/i.test(c.name ?? '')) ??
    list.find((c) => /general|walk-?in|cash/i.test(c.no ?? '')) ??
    list[0]
  return walkIn?.id ?? null
}

export function RestaurantCounterCheckoutDialog({
  open,
  orderId,
  total,
  mode = 'counter',
  initialCustomerId = null,
  combineOrdersAvailable = false,
  checkId = null,
  onClose,
  onSuccess,
}: Props) {
  const { printReport, printing: printingReceipt } = useReceiptReportPrint()
  const [methods, setMethods] = useState<POSPaymentMethod[]>([])
  const [customers, setCustomers] = useState<POSCustomer[]>([])
  const [methodId, setMethodId] = useState<number | null>(null)
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [combineOrders, setCombineOrders] = useState(false)
  const [amountTendered, setAmountTendered] = useState('')
  const [loading, setLoading] = useState(false)

  const isDineIn = mode === 'dine_in'

  useEffect(() => {
    if (!open) return
    void salesService.getPaymentMethods().then((list) => {
      setMethods(list)
      setMethodId(list[0]?.id ?? null)
    })
    void salesService.getCustomers().then((list) => {
      setCustomers(list)
      setCustomerId(pickDefaultCustomerId(list, initialCustomerId))
    })
    setAmountTendered(String(total))
    setCombineOrders(false)
  }, [open, total, initialCustomerId])

  if (!open) return null

  const selected = methods.find((m) => m.id === methodId)
  const requiresTendered = selected?.requires_amount_received ?? false
  const tendered = Number(parseNumericInput(amountTendered) || 0)
  const change = Math.max(0, tendered - total)

  const handlePay = async () => {
    if (!methodId) {
      toast.error('Select a payment method')
      return
    }
    if (!customerId) {
      toast.error('Select a customer to bill')
      return
    }
    setLoading(true)
    try {
      let invoiceSystemId: string | null = null
      let orderCompleted = true
      if (isDineIn) {
        const res = await restaurantService.checkoutAndPost(orderId, {
          payment_method_id: methodId,
          customer_id: customerId,
          combine_orders: checkId != null ? false : combineOrders,
          check_id: checkId ?? undefined,
          amount_received: requiresTendered ? tendered : total,
          change_amount: requiresTendered ? change : null,
        })
        invoiceSystemId = String((res.invoice as { system_id?: string }).system_id ?? '')
        orderCompleted = res.order_completed !== false
      } else {
        const res = await restaurantService.counterCheckout(orderId, {
          payment_method_id: methodId,
          customer_id: customerId,
          amount_received: requiresTendered ? tendered : null,
          change_amount: requiresTendered ? change : null,
        })
        invoiceSystemId = String((res.invoice as { system_id?: string }).system_id ?? '')
      }
      toast.success(orderCompleted ? 'Payment completed' : 'Split check paid — remaining balance still open')
      if (invoiceSystemId) {
        try {
          await printReport(ReceiptReportId.SALES_RECEIPT, {
            invoice_system_id: invoiceSystemId,
            process: 'restaurant_settle',
          })
        } catch (printErr) {
          console.error(printErr)
          toast.warning('Payment recorded — receipt did not print')
        }
      }
      onSuccess({ orderCompleted })
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Payment failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold text-mainTextColor">
          {isDineIn
            ? checkId != null
              ? 'Pay split check'
              : 'Close check & pay'
            : 'Counter checkout'}
        </h3>
        <p className="mt-1 text-2xl font-bold text-s1">{formatDecimalDisplay(total)}</p>

        <label className="mt-4 block text-sm font-medium text-bodyText">
          {isDineIn ? 'Bill to' : 'Customer'}
        </label>
        <select
          value={customerId ?? ''}
          onChange={(e) => setCustomerId(Number(e.target.value))}
          className="mt-1 w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
        >
          {customers.length === 0 ? (
            <option value="">No customers found — create one in Customers</option>
          ) : (
            customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.no ? ` (${c.no})` : ''}
              </option>
            ))
          )}
        </select>
        {isDineIn && combineOrdersAvailable && checkId == null ? (
          <label className="mt-3 flex items-center gap-2 text-sm text-bodyText">
            <input
              type="checkbox"
              checked={combineOrders}
              onChange={(e) => setCombineOrders(e.target.checked)}
              className="rounded border-strokeColor"
            />
            Combine all served checks on this table into one bill
          </label>
        ) : null}

        <label className="mt-4 block text-sm font-medium text-bodyText">Payment method</label>
        <select
          value={methodId ?? ''}
          onChange={(e) => setMethodId(Number(e.target.value))}
          className="mt-1 w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
        >
          {methods.map((m) => (
            <option key={m.id} value={m.id}>
              {m.description || m.code}
            </option>
          ))}
        </select>

        {requiresTendered ? (
          <>
            <label className="mt-3 block text-sm font-medium text-bodyText">Amount received</label>
            <input
              type="text"
              inputMode="decimal"
              value={amountTendered}
              onChange={(e) => setAmountTendered(formatAmountInput(e.target.value))}
              className="mt-1 w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
            />
            <p className="mt-2 text-sm text-bodyText">Change: {formatDecimalDisplay(change)}</p>
          </>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-lg border border-strokeColor px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handlePay()}
            disabled={loading}
            className="rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {loading ? 'Processing…' : 'Pay & post'}
          </button>
        </div>
      </div>
    </div>
  )
}
