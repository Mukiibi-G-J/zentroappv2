'use client'

import { useEffect, useState } from 'react'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { POSCartLine } from '@/types/pos'

interface POSCartPanelProps {
  cart: POSCartLine[]
  subtotal: number
  onUpdateQuantity: (clientId: string, quantity: number) => void
  onRemove: (clientId: string) => void
  onClear: () => void
  onCheckout: () => void
  onSelectTracking?: (clientId: string) => void
  lineRequiresTracking?: (line: POSCartLine) => boolean
  compact?: boolean
}

function QuantityStepper({
  quantity,
  onChange,
}: {
  quantity: number
  onChange: (quantity: number) => void
}) {
  const [draft, setDraft] = useState(String(quantity))

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
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label="Decrease quantity"
        className="h-8 w-8 rounded-lg border border-strokeColor text-lg leading-none"
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
        onChange={(e) => {
          const next = e.target.value.replace(/[^\d]/g, '')
          setDraft(next)
        }}
        onBlur={() => commit(draft)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.currentTarget.blur()
          }
        }}
        onFocus={(e) => e.target.select()}
        className="h-8 w-10 rounded-lg border border-strokeColor bg-white text-center text-sm font-medium text-mainTextColor outline-none focus:border-s1 focus:ring-1 focus:ring-s1"
      />
      <button
        type="button"
        aria-label="Increase quantity"
        className="h-8 w-8 rounded-lg border border-strokeColor text-lg leading-none"
        onClick={() => onChange(quantity + 1)}
      >
        +
      </button>
    </div>
  )
}

export function POSCartPanel({
  cart,
  subtotal,
  onUpdateQuantity,
  onRemove,
  onClear,
  onCheckout,
  onSelectTracking,
  lineRequiresTracking,
  compact,
}: POSCartPanelProps) {
  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-strokeColor bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-strokeColor px-4 py-3">
        <h2 className="text-sm font-semibold text-mainTextColor">Current sale</h2>
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

      <div className="min-h-0 flex-1 overflow-y-auto">
        {cart.length === 0 ? (
          <p className="p-6 text-center text-sm text-bodyText">Tap products to add them here.</p>
        ) : (
          <ul className="divide-y divide-strokeColor">
            {cart.map((line) => {
              const needsTracking = lineRequiresTracking?.(line) ?? false
              const missingLot = needsTracking && !line.selectedLotNo?.trim()
              return (
                <li key={line.clientId} className="flex items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-mainTextColor">{line.name}</p>
                    <p className="text-xs text-bodyText">{formatDecimalDisplay(line.unitPrice)} each</p>
                    {needsTracking && (
                      <button
                        type="button"
                        onClick={() => onSelectTracking?.(line.clientId)}
                        className={`mt-1 text-xs font-medium hover:underline ${
                          missingLot ? 'text-amber-700' : 'text-s1'
                        }`}
                      >
                        {line.selectedLotNo ? `Lot ${line.selectedLotNo}` : 'Select lot *'}
                      </button>
                    )}
                  </div>
                  <QuantityStepper
                    quantity={line.quantity}
                    onChange={(qty) => onUpdateQuantity(line.clientId, qty)}
                  />
                  <div className="text-right">
                    <p className="text-sm font-semibold text-mainTextColor">
                      {formatDecimalDisplay(line.quantity * line.unitPrice - line.lineDiscountAmount)}
                    </p>
                    <button
                      type="button"
                      onClick={() => onRemove(line.clientId)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-strokeColor p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-bodyText">Total</span>
          <span className="text-xl font-bold text-mainTextColor">{formatDecimalDisplay(subtotal)}</span>
        </div>
        <button
          type="button"
          disabled={!cart.length}
          onClick={onCheckout}
          className={`w-full rounded-xl bg-s1 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
            compact ? 'py-3.5' : ''
          }`}
        >
          Charge {cart.length ? formatDecimalDisplay(subtotal) : ''}
        </button>
      </div>
    </div>
  )
}
