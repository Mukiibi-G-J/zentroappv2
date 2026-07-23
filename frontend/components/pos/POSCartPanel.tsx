'use client'

import { useEffect, useRef, useState } from 'react'
import { Pencil, Percent, Trash2, X } from 'lucide-react'
import {
  formatAmountDisplay,
  formatAmountInput,
  formatDecimalDisplay,
  parseNumericInput,
} from '@/lib/formatNumber'
import type { POSCartLine } from '@/types/pos'

interface POSCartPanelProps {
  cart: POSCartLine[]
  /** Line subtotal after line discounts (before payment/invoice discount). */
  subtotal: number
  /** Payable total after payment/invoice discount. */
  total: number
  canEditPrice?: boolean
  enableLineDiscounts?: boolean
  enableInvoiceDiscounts?: boolean
  invoiceDiscountType?: 'amount' | 'percentage'
  invoiceDiscountAmount?: number
  invoiceDiscountPercentage?: number
  invoiceDiscountValue?: number
  onUpdateQuantity: (clientId: string, quantity: number) => void
  onUpdatePrice?: (clientId: string, unitPrice: number) => void
  onUpdateLineDiscount?: (clientId: string, discount: number) => void
  onInvoiceDiscountTypeChange?: (type: 'amount' | 'percentage') => void
  onInvoiceDiscountAmountChange?: (amount: number) => void
  onInvoiceDiscountPercentageChange?: (percentage: number) => void
  onRemove: (clientId: string) => void
  onClear: () => void
  onCheckout: () => void
  onSelectTracking?: (clientId: string) => void
  lineRequiresTracking?: (line: POSCartLine) => boolean
  compact?: boolean
}

function parseAmount(raw: string): number {
  const cleaned = parseNumericInput(raw).replace(/[^\d.]/g, '')
  return Number.parseFloat(cleaned)
}

function QuantityStepper({
  quantity,
  onChange,
  size = 'md',
}: {
  quantity: number
  onChange: (quantity: number) => void
  size?: 'sm' | 'md'
}) {
  const [draft, setDraft] = useState(String(quantity))
  const btn = size === 'sm' ? 'h-8 w-8 text-lg' : 'h-9 w-9 text-lg'
  const input = size === 'sm' ? 'h-8 w-10 text-sm' : 'h-9 w-11 text-sm'

  useEffect(() => {
    setDraft(String(quantity))
  }, [quantity])

  const commit = (raw: string) => {
    const parsed = Number.parseInt(raw, 10)
    if (!Number.isFinite(parsed) || parsed < 1) {
      setDraft(String(quantity))
      return
    }
    onChange(parsed)
  }

  return (
    <div className="flex shrink-0 items-center gap-0.5">
      <button
        type="button"
        aria-label="Decrease quantity"
        className={`${btn} rounded-md border border-strokeColor leading-none`}
        onClick={() => onChange(quantity - 1)}
      >
        −
      </button>
      <input
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        aria-label="Quantity"
        value={draft}
        onChange={(e) => setDraft(e.target.value.replace(/[^\d]/g, ''))}
        onBlur={() => commit(draft)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur()
        }}
        onFocus={(e) => e.target.select()}
        className={`${input} rounded-md border border-strokeColor bg-white text-center font-medium text-mainTextColor outline-none focus:border-s1 focus:ring-1 focus:ring-s1`}
      />
      <button
        type="button"
        aria-label="Increase quantity"
        className={`${btn} rounded-md border border-strokeColor leading-none`}
        onClick={() => onChange(quantity + 1)}
      >
        +
      </button>
    </div>
  )
}

function SheetShell({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="pos-sheet-title"
        className="relative w-full max-w-md rounded-t-2xl bg-white shadow-xl sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-strokeColor px-4 py-3">
          <h3 id="pos-sheet-title" className="truncate pr-3 text-sm font-semibold text-mainTextColor">
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-bodyText hover:bg-softBg"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  )
}

function EditLineSheet({
  line,
  canEditPrice,
  enableLineDiscounts,
  onClose,
  onUpdatePrice,
  onUpdateLineDiscount,
  onUpdateQuantity,
  onRemove,
  onSelectTracking,
  needsTracking,
  missingTracking,
  trackingLabel,
}: {
  line: POSCartLine
  canEditPrice?: boolean
  enableLineDiscounts?: boolean
  onClose: () => void
  onUpdatePrice?: (clientId: string, unitPrice: number) => void
  onUpdateLineDiscount?: (clientId: string, discount: number) => void
  onUpdateQuantity: (clientId: string, quantity: number) => void
  onRemove: (clientId: string) => void
  onSelectTracking?: (clientId: string) => void
  needsTracking: boolean
  missingTracking: boolean
  trackingLabel: string
}) {
  const gross = line.quantity * line.unitPrice
  const [priceDraft, setPriceDraft] = useState(formatAmountDisplay(line.unitPrice))
  const [discDraft, setDiscDraft] = useState(
    line.lineDiscountAmount > 0 ? formatAmountDisplay(line.lineDiscountAmount) : '',
  )

  useEffect(() => {
    setPriceDraft(formatAmountDisplay(line.unitPrice))
  }, [line.unitPrice])

  useEffect(() => {
    setDiscDraft(
      line.lineDiscountAmount > 0 ? formatAmountDisplay(line.lineDiscountAmount) : '',
    )
  }, [line.lineDiscountAmount])

  const commitPrice = () => {
    const parsed = parseAmount(priceDraft)
    if (!Number.isFinite(parsed) || parsed < 0) {
      setPriceDraft(formatAmountDisplay(line.unitPrice))
      return
    }
    let next = Math.round(parsed * 100) / 100
    const disc = line.lineDiscountAmount || 0
    if (disc > 0 && line.quantity > 0 && next * line.quantity < disc) {
      next = Math.round((disc / line.quantity) * 100) / 100
      setPriceDraft(formatAmountDisplay(next))
    }
    onUpdatePrice?.(line.clientId, next)
  }

  const commitDiscount = () => {
    const parsed = parseAmount(discDraft || '0')
    if (!Number.isFinite(parsed) || parsed < 0) {
      setDiscDraft(
        line.lineDiscountAmount > 0 ? formatAmountDisplay(line.lineDiscountAmount) : '',
      )
      return
    }
    const clamped = Math.min(parsed, Math.max(0, gross))
    onUpdateLineDiscount?.(line.clientId, clamped)
    setDiscDraft(clamped > 0 ? formatAmountDisplay(clamped) : '')
  }

  return (
    <SheetShell open title={line.name} onClose={onClose}>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-bodyText">Quantity</span>
          <QuantityStepper
            quantity={line.quantity}
            onChange={(qty) => onUpdateQuantity(line.clientId, qty)}
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-bodyText">Unit price</label>
          {canEditPrice ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                value={priceDraft}
                onChange={(e) => setPriceDraft(formatAmountInput(e.target.value))}
                onBlur={commitPrice}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') e.currentTarget.blur()
                }}
                onFocus={(e) => e.target.select()}
                className="h-10 w-full rounded-xl border border-strokeColor px-3 text-sm outline-none focus:border-s1 focus:ring-1 focus:ring-s1"
              />
              <span className="shrink-0 text-xs text-bodyText">each</span>
            </div>
          ) : (
            <p className="text-sm font-medium text-mainTextColor">
              {formatAmountDisplay(line.unitPrice)} each
            </p>
          )}
        </div>

        {enableLineDiscounts && onUpdateLineDiscount && (
          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">Line discount</label>
            <input
              type="text"
              inputMode="decimal"
              placeholder="0"
              value={discDraft}
              onChange={(e) => setDiscDraft(formatAmountInput(e.target.value))}
              onBlur={commitDiscount}
              onFocus={(e) => e.target.select()}
              className="h-10 w-full rounded-xl border border-strokeColor px-3 text-sm outline-none focus:border-s1 focus:ring-1 focus:ring-s1"
            />
          </div>
        )}

        {needsTracking && (
          <button
            type="button"
            onClick={() => {
              onSelectTracking?.(line.clientId)
              onClose()
            }}
            className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm font-medium ${
              missingTracking
                ? 'border-amber-300 bg-amber-50 text-amber-800'
                : 'border-strokeColor bg-softBg text-s1'
            }`}
          >
            {trackingLabel}
          </button>
        )}

        <div className="flex items-center justify-between border-t border-strokeColor pt-3 text-sm">
          <span className="text-bodyText">Line total</span>
          <span className="font-semibold text-mainTextColor">
            {formatDecimalDisplay(Math.max(0, gross - (line.lineDiscountAmount || 0)))}
          </span>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={() => {
              onRemove(line.clientId)
              onClose()
            }}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-red-200 bg-red-50 py-2.5 text-sm font-medium text-red-700"
          >
            <Trash2 className="h-4 w-4" />
            Remove
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl bg-s1 py-2.5 text-sm font-semibold text-white"
          >
            Done
          </button>
        </div>
      </div>
    </SheetShell>
  )
}

function PaymentDiscountSheet({
  open,
  onClose,
  subtotal,
  invoiceDiscountType,
  invoiceDiscountAmount,
  invoiceDiscountPercentage,
  invoiceDiscountValue,
  onInvoiceDiscountTypeChange,
  onInvoiceDiscountAmountChange,
  onInvoiceDiscountPercentageChange,
}: {
  open: boolean
  onClose: () => void
  subtotal: number
  invoiceDiscountType: 'amount' | 'percentage'
  invoiceDiscountAmount: number
  invoiceDiscountPercentage: number
  invoiceDiscountValue: number
  onInvoiceDiscountTypeChange?: (type: 'amount' | 'percentage') => void
  onInvoiceDiscountAmountChange?: (amount: number) => void
  onInvoiceDiscountPercentageChange?: (percentage: number) => void
}) {
  return (
    <SheetShell open={open} title="Payment discount" onClose={onClose}>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={invoiceDiscountType}
            onChange={(e) =>
              onInvoiceDiscountTypeChange?.(e.target.value as 'amount' | 'percentage')
            }
            className="h-10 rounded-xl border border-strokeColor bg-white px-3 text-sm"
          >
            <option value="amount">Amount</option>
            <option value="percentage">%</option>
          </select>
          {invoiceDiscountType === 'amount' ? (
            <input
              type="text"
              inputMode="decimal"
              aria-label="Payment discount amount"
              value={invoiceDiscountAmount > 0 ? formatAmountDisplay(invoiceDiscountAmount) : ''}
              onChange={(e) =>
                onInvoiceDiscountAmountChange?.(parseAmount(e.target.value || '0') || 0)
              }
              onBlur={(e) => {
                const n = Math.min(
                  Math.max(0, parseAmount(e.target.value || '0') || 0),
                  subtotal,
                )
                onInvoiceDiscountAmountChange?.(n)
              }}
              className="h-10 min-w-0 flex-1 rounded-xl border border-strokeColor bg-white px-3 text-right text-sm"
            />
          ) : (
            <input
              type="text"
              inputMode="decimal"
              aria-label="Payment discount percent"
              value={invoiceDiscountPercentage > 0 ? String(invoiceDiscountPercentage) : ''}
              onChange={(e) => {
                const n = Math.min(100, Math.max(0, parseAmount(e.target.value || '0') || 0))
                onInvoiceDiscountPercentageChange?.(n)
              }}
              className="h-10 w-24 rounded-xl border border-strokeColor bg-white px-3 text-right text-sm"
            />
          )}
        </div>
        {invoiceDiscountValue > 0 && (
          <p className="text-sm text-red-600">−{formatDecimalDisplay(invoiceDiscountValue)}</p>
        )}
        <button
          type="button"
          onClick={onClose}
          className="w-full rounded-xl bg-s1 py-2.5 text-sm font-semibold text-white"
        >
          Done
        </button>
      </div>
    </SheetShell>
  )
}

export function POSCartPanel({
  cart,
  subtotal,
  total,
  canEditPrice,
  enableLineDiscounts,
  enableInvoiceDiscounts,
  invoiceDiscountType = 'amount',
  invoiceDiscountAmount = 0,
  invoiceDiscountPercentage = 0,
  invoiceDiscountValue = 0,
  onUpdateQuantity,
  onUpdatePrice,
  onUpdateLineDiscount,
  onInvoiceDiscountTypeChange,
  onInvoiceDiscountAmountChange,
  onInvoiceDiscountPercentageChange,
  onRemove,
  onClear,
  onCheckout,
  onSelectTracking,
  lineRequiresTracking,
  compact,
}: POSCartPanelProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const prevCountRef = useRef(cart.length)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [discountOpen, setDiscountOpen] = useState(false)

  const editingLine = editingId ? cart.find((l) => l.clientId === editingId) : undefined

  useEffect(() => {
    if (cart.length > prevCountRef.current) {
      const el = listRef.current
      if (el) el.scrollTop = el.scrollHeight
    }
    prevCountRef.current = cart.length
  }, [cart.length])

  useEffect(() => {
    if (editingId && !cart.some((l) => l.clientId === editingId)) {
      setEditingId(null)
    }
  }, [cart, editingId])

  const canEditLine =
    Boolean(canEditPrice) || Boolean(enableLineDiscounts) || Boolean(onSelectTracking)

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-strokeColor bg-white shadow-sm">
      <div className="flex shrink-0 items-center justify-between border-b border-strokeColor px-3 py-2.5">
        <h2 className="text-sm font-semibold text-mainTextColor">
          Current sale
          {cart.length > 0 && (
            <span className="ml-1.5 font-normal text-bodyText">({cart.length})</span>
          )}
        </h2>
        {cart.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="text-xs font-medium text-red-600 hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {cart.length === 0 ? (
          <p className="p-6 text-center text-sm text-bodyText">Tap products to add them here.</p>
        ) : (
          <ul className="divide-y divide-strokeColor">
            {cart.map((line) => {
              const needsTracking = lineRequiresTracking?.(line) ?? false
              const needsSerial = Boolean(line.trackingCode?.require_serial_no)
              const serials = line.selectedSerialNos ?? []
              const trackingOk = needsSerial
                ? serials.length === line.quantity && serials.every((s) => s.trim())
                : Boolean(line.selectedLotNo?.trim())
              const missingTracking = needsTracking && !trackingOk
              const trackingLabel = needsSerial
                ? serials.length
                  ? `SN ${serials.slice(0, 2).join(', ')}${serials.length > 2 ? '…' : ''}`
                  : 'Select serial *'
                : line.selectedLotNo
                  ? `Lot ${line.selectedLotNo}`
                  : 'Select lot *'
              const gross = line.quantity * line.unitPrice
              const disc = Math.min(line.lineDiscountAmount || 0, Math.max(0, gross))
              const net = gross - disc
              const hasDisc = disc > 0

              return (
                <li key={line.clientId} className="flex items-center gap-2.5 px-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => setEditingId(line.clientId)}
                      className="w-full text-left"
                      title={canEditLine ? 'Edit line' : line.name}
                    >
                      <p className="truncate text-[15px] font-medium leading-snug text-mainTextColor">
                        {line.name}
                      </p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs leading-tight text-bodyText">
                        <span>{formatAmountDisplay(line.unitPrice)} ea</span>
                        {hasDisc && (
                          <span className="text-red-600">
                            −{formatAmountDisplay(disc)}
                          </span>
                        )}
                        {canEditLine && (
                          <span className="inline-flex items-center gap-1 text-bodyText/80">
                            <Pencil className="h-3 w-3" />
                            Edit
                          </span>
                        )}
                      </p>
                    </button>
                    {needsTracking && (
                      <button
                        type="button"
                        onClick={() => onSelectTracking?.(line.clientId)}
                        className={`mt-1 text-left text-xs font-medium hover:underline ${
                          missingTracking ? 'text-amber-700' : 'text-s1'
                        }`}
                      >
                        {trackingLabel}
                      </button>
                    )}
                  </div>

                  <QuantityStepper
                    size="sm"
                    quantity={line.quantity}
                    onChange={(qty) => onUpdateQuantity(line.clientId, qty)}
                  />

                  <div className="w-20 shrink-0 text-right">
                    <p className="text-[15px] font-semibold tabular-nums text-mainTextColor">
                      {formatDecimalDisplay(net)}
                    </p>
                    <button
                      type="button"
                      onClick={() => onRemove(line.clientId)}
                      className="mt-1 inline-flex text-red-500 hover:text-red-700"
                      aria-label={`Remove ${line.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="shrink-0 border-t border-strokeColor bg-white p-3">
        {enableInvoiceDiscounts && cart.length > 0 && (
          <button
            type="button"
            onClick={() => setDiscountOpen(true)}
            className="mb-2 flex w-full items-center justify-between rounded-lg border border-strokeColor bg-softBg px-3 py-2 text-left text-xs"
          >
            <span className="inline-flex items-center gap-1.5 font-medium text-bodyText">
              <Percent className="h-3.5 w-3.5" />
              Payment discount
            </span>
            <span className={invoiceDiscountValue > 0 ? 'font-medium text-red-600' : 'text-bodyText'}>
              {invoiceDiscountValue > 0
                ? `−${formatDecimalDisplay(invoiceDiscountValue)}`
                : 'Add'}
            </span>
          </button>
        )}

        <div className="mb-2 space-y-0.5">
          {enableInvoiceDiscounts && invoiceDiscountValue > 0 && (
            <div className="flex items-center justify-between text-xs text-bodyText">
              <span>Subtotal</span>
              <span>{formatDecimalDisplay(subtotal)}</span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-sm text-bodyText">Total</span>
            <span className="text-xl font-bold tabular-nums text-mainTextColor">
              {formatDecimalDisplay(total)}
            </span>
          </div>
        </div>

        <button
          type="button"
          disabled={!cart.length}
          onClick={onCheckout}
          className={`w-full rounded-xl bg-s1 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
            compact ? 'py-3.5' : ''
          }`}
        >
          Charge {cart.length ? formatDecimalDisplay(total) : ''}
        </button>
      </div>

      {editingLine && (
        <EditLineSheet
          line={editingLine}
          canEditPrice={canEditPrice}
          enableLineDiscounts={enableLineDiscounts}
          onClose={() => setEditingId(null)}
          onUpdatePrice={onUpdatePrice}
          onUpdateLineDiscount={onUpdateLineDiscount}
          onUpdateQuantity={onUpdateQuantity}
          onRemove={onRemove}
          onSelectTracking={onSelectTracking}
          needsTracking={lineRequiresTracking?.(editingLine) ?? false}
          missingTracking={(() => {
            const needs = lineRequiresTracking?.(editingLine) ?? false
            if (!needs) return false
            const needsSerial = Boolean(editingLine.trackingCode?.require_serial_no)
            const serials = editingLine.selectedSerialNos ?? []
            return needsSerial
              ? !(serials.length === editingLine.quantity && serials.every((s) => s.trim()))
              : !Boolean(editingLine.selectedLotNo?.trim())
          })()}
          trackingLabel={(() => {
            const needsSerial = Boolean(editingLine.trackingCode?.require_serial_no)
            const serials = editingLine.selectedSerialNos ?? []
            if (needsSerial) {
              return serials.length ? `SN ${serials.join(', ')}` : 'Select serial *'
            }
            return editingLine.selectedLotNo
              ? `Lot ${editingLine.selectedLotNo}`
              : 'Select lot *'
          })()}
        />
      )}

      {enableInvoiceDiscounts && (
        <PaymentDiscountSheet
          open={discountOpen}
          onClose={() => setDiscountOpen(false)}
          subtotal={subtotal}
          invoiceDiscountType={invoiceDiscountType}
          invoiceDiscountAmount={invoiceDiscountAmount}
          invoiceDiscountPercentage={invoiceDiscountPercentage}
          invoiceDiscountValue={invoiceDiscountValue}
          onInvoiceDiscountTypeChange={onInvoiceDiscountTypeChange}
          onInvoiceDiscountAmountChange={onInvoiceDiscountAmountChange}
          onInvoiceDiscountPercentageChange={onInvoiceDiscountPercentageChange}
        />
      )}
    </div>
  )
}
