'use client'

import { useEffect, useMemo, useState } from 'react'
import { Banknote, Clock, Smartphone, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { salesService } from '@/services/sales.service'
import type { POSPaymentMethod } from '@/types/pos'

interface Props {
  open: boolean
  onClose: () => void
  onSelect: (code: string) => void | Promise<void>
  saving?: boolean
  subtitle?: string
  /** Highlight the current header selection when confirming before post. */
  selectedCode?: string
}

const METHOD_ORDER = ['NOT_PAID', 'CASH', 'MOBILE_MONEY', 'BANK']

function friendlyLabel(method: POSPaymentMethod): string {
  const labels: Record<string, string> = {
    NOT_PAID: 'Pay later',
    CASH: 'Cash',
    MOBILE_MONEY: 'Mobile Money',
    BANK: 'Bank',
  }
  return labels[method.code] ?? method.description ?? method.code
}

function methodHint(method: POSPaymentMethod): string {
  if (method.code === 'NOT_PAID') return 'Record as amount owed to the vendor'
  if (method.code === 'CASH') return 'Paid immediately from cash'
  if (method.code === 'MOBILE_MONEY') return 'Paid via mobile money'
  return method.description ?? 'Paid immediately'
}

function MethodIcon({ code }: { code: string }) {
  if (code === 'NOT_PAID') return <Clock size={22} className="text-bodyText" />
  if (code === 'MOBILE_MONEY') return <Smartphone size={22} className="text-bodyText" />
  return <Banknote size={22} className="text-bodyText" />
}

export default function PaymentMethodPickDialog({
  open,
  onClose,
  onSelect,
  saving,
  subtitle = 'Choose one option to continue.',
  selectedCode,
}: Props) {
  const [methods, setMethods] = useState<POSPaymentMethod[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    void salesService.getPaymentMethods().then((list) => {
      if (!cancelled) {
        setMethods(list)
        setLoading(false)
      }
    }).catch(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [open])

  const sortedMethods = useMemo(() => {
    const order = new Map(METHOD_ORDER.map((code, index) => [code, index]))
    return [...methods].sort((a, b) => {
      const ai = order.get(a.code) ?? 99
      const bi = order.get(b.code) ?? 99
      if (ai !== bi) return ai - bi
      return a.description.localeCompare(b.description)
    })
  }, [methods])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={saving ? undefined : onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-base font-semibold text-mainTextColor">How did you pay?</h2>
            <p className="mt-1 text-sm text-bodyText">{subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-bodyText transition shrink-0 disabled:opacity-50"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-3">
          {loading ? (
            <p className="text-sm text-bodyText text-center py-6">Loading payment options…</p>
          ) : sortedMethods.length === 0 ? (
            <p className="text-sm text-bodyText text-center py-6">
              No payment methods are set up. Ask your administrator to configure them.
            </p>
          ) : (
            sortedMethods.map((method) => {
              const isSelected = selectedCode != null
                && method.code.trim().toUpperCase() === selectedCode.trim().toUpperCase()
              return (
              <button
                key={method.id}
                type="button"
                disabled={saving}
                onClick={() => void onSelect(method.code)}
                className={cn(
                  'w-full flex items-start gap-4 rounded-xl border px-4 py-4 text-left transition',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  isSelected
                    ? 'border-s1 bg-s1/10 ring-1 ring-s1/30'
                    : 'border-gray-200 hover:border-s1 hover:bg-s1/5',
                )}
              >
                <div className="mt-0.5 shrink-0">
                  <MethodIcon code={method.code} />
                </div>
                <div className="min-w-0">
                  <div className="text-base font-semibold text-mainTextColor">
                    {friendlyLabel(method)}
                  </div>
                  <div className="text-sm text-bodyText mt-0.5">{methodHint(method)}</div>
                </div>
              </button>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
