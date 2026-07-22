'use client'

import { useEffect, useMemo, useState } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import SearchableRelationSelect from '@/components/dynamic/SearchableRelationSelect'
import RelationLookupModal from '@/components/dynamic/RelationLookupModal'
import DatePicker from '@/components/ui/DatePicker'
import { usePages } from '@/hooks/usePage'
import { formatAmountDisplay, formatAmountInput, parseNumericInput } from '@/lib/formatNumber'
import { PAGE_IDS } from '@/lib/pageIds'
import { salesService } from '@/services/sales.service'
import type { RelationOption } from '@/hooks/useRelationOptions'
import type { RelationMenuFooter } from '@/lib/relationMenuFooter'
import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import type { POSCustomer, POSPaymentMethod } from '@/types/pos'

/** Synthetic field so RelationLookupModal can return Customer.id as the selected value. */
const POS_CUSTOMER_LOOKUP_FIELD: PageControlField = {
  FieldId: 0,
  PageId: 0,
  PageControlId: 0,
  PageControlFieldId: 0,
  Name: 'customer',
  Caption: 'Customer',
  FieldType: 'Code',
  Visible: true,
  Editable: true,
  PrimaryKey: false,
  Required: false,
  TabIndex: 0,
  RelatedTable: 'Customer',
  RelatedField: 'no',
}

function customerToOption(c: POSCustomer): RelationOption {
  return {
    value: String(c.id),
    label: `${c.name} (${c.no})`,
    caption: c.name,
    name: c.name,
  }
}

async function resolveCustomerFromLookup(
  record: DataRecord,
  fallbackList: POSCustomer[],
): Promise<POSCustomer | null> {
  const id = Number(record.id)
  if (Number.isFinite(id) && id > 0) {
    const fromList = fallbackList.find((c) => c.id === id)
    if (fromList) return fromList
    return {
      id,
      no: String(record.no ?? ''),
      name: String(record.name ?? ''),
      payment_method:
        record.payment_method != null && record.payment_method !== ''
          ? Number(record.payment_method)
          : null,
      customer_type:
        record.customer_type != null && record.customer_type !== ''
          ? String(record.customer_type)
          : null,
    }
  }

  const no = String(record.no ?? '').trim()
  const name = String(record.name ?? '').trim()
  const matchIn = (list: POSCustomer[]) =>
    (no ? list.find((c) => c.no === no) : undefined) ??
    (name ? list.find((c) => c.name === name) : undefined) ??
    null

  const existing = matchIn(fallbackList)
  if (existing) return existing

  try {
    const fresh = await salesService.getCustomers()
    return matchIn(fresh)
  } catch {
    return null
  }
}

interface POSCheckoutDialogProps {
  open: boolean
  subtotal: number
  amountReceived: number
  onAmountReceivedChange: (value: number) => void
  customers: POSCustomer[]
  selectedCustomer: POSCustomer | null
  onCustomerChange: (customer: POSCustomer) => void
  onCustomersRefresh?: () => void | Promise<void>
  paymentMethods: POSPaymentMethod[]
  selectedPaymentMethod: POSPaymentMethod | null
  onPaymentMethodChange: (method: POSPaymentMethod) => void
  isGeneralCustomer: boolean
  saleDate: string
  onSaleDateChange: (value: string) => void
  canPostPreviousDates: boolean
  loading?: boolean
  onClose: () => void
  onConfirm: () => void
}

function todayIsoDate(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function POSCheckoutDialog({
  open,
  subtotal,
  amountReceived,
  onAmountReceivedChange,
  customers,
  selectedCustomer,
  onCustomerChange,
  onCustomersRefresh,
  paymentMethods,
  selectedPaymentMethod,
  onPaymentMethodChange,
  isGeneralCustomer,
  saleDate,
  onSaleDateChange,
  canPostPreviousDates,
  loading,
  onClose,
  onConfirm,
}: POSCheckoutDialogProps) {
  // Keep a string draft so the user can clear/edit freely without immediate re-formatting.
  const [amountDraft, setAmountDraft] = useState('')
  const [lookupMode, setLookupMode] = useState<'list' | 'new' | null>(null)
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const posReturnPath = useMemo(() => {
    const qs = searchParams.toString()
    return qs ? `${pathname}?${qs}` : pathname
  }, [pathname, searchParams])

  const { data: allPages = [] } = usePages()
  const customerListPage = useMemo(
    () =>
      allPages.find((p) => p.Name === 'CustomerList') ??
      allPages.find((p) => p.PageId === PAGE_IDS.CUSTOMERS),
    [allPages],
  )

  useEffect(() => {
    if (!open) return
    // Prefill once when the dialog opens; keep a string draft while the user edits.
    setAmountDraft(formatAmountDisplay(subtotal))
    setLookupMode(null)
    // Intentionally omit `subtotal` so edits are not wiped if totals recompute while open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const customerOptions = useMemo(() => {
    const opts = customers.map(customerToOption)
    if (
      selectedCustomer &&
      !opts.some((o) => o.value === String(selectedCustomer.id))
    ) {
      opts.unshift(customerToOption(selectedCustomer))
    }
    return opts
  }, [customers, selectedCustomer])

  const customerMenuFooter = useMemo((): RelationMenuFooter | undefined => {
    if (!customerListPage) return undefined
    return {
      onNew: () => setLookupMode('new'),
      onSelectFromFullList: () => setLookupMode('list'),
    }
  }, [customerListPage])

  if (!open) return null

  const requiresTender = selectedPaymentMethod?.requires_amount_received !== false
  const change = requiresTender ? Math.max(0, amountReceived - subtotal) : 0

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <h2 className="text-lg font-semibold text-mainTextColor">Complete payment</h2>
          <button type="button" onClick={onClose} className="text-sm text-bodyText hover:text-mainTextColor">
            Close
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">Customer</label>
            <SearchableRelationSelect
              options={customerOptions}
              value={selectedCustomer ? String(selectedCustomer.id) : ''}
              placeholder="Search customer…"
              menuFooter={customerMenuFooter}
              onChange={(value) => {
                const c =
                  customers.find((x) => String(x.id) === value) ??
                  (selectedCustomer && String(selectedCustomer.id) === value
                    ? selectedCustomer
                    : null)
                if (c) onCustomerChange(c)
              }}
              noOptionsMessage="No customers found"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">Payment method</label>
            <select
              className="w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
              value={selectedPaymentMethod?.id ?? ''}
              onChange={(e) => {
                const m = paymentMethods.find((x) => x.id === Number(e.target.value))
                if (m) {
                  if (isGeneralCustomer && m.code === 'NOT_PAID') return
                  onPaymentMethodChange(m)
                }
              }}
            >
              {paymentMethods
                .filter((m) => !(isGeneralCustomer && m.code === 'NOT_PAID'))
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.description}
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">Sale date</label>
            <DatePicker
              value={saleDate}
              className="border-strokeColor py-0.5"
              onChange={(selected) => {
                if (!selected) return
                const today = todayIsoDate()
                if (!canPostPreviousDates && selected < today) return
                onSaleDateChange(selected)
              }}
            />
            {!canPostPreviousDates ? (
              <p className="mt-1 text-xs text-bodyText">
                You cannot post sales for previous dates
              </p>
            ) : null}
          </div>

          <div className="rounded-xl bg-softBg p-4">
            <div className="flex justify-between text-sm">
              <span className="text-bodyText">Total due</span>
              <span className="font-semibold text-mainTextColor">{formatAmountDisplay(subtotal)}</span>
            </div>
            {requiresTender && (
              <>
                <div className="mt-3">
                  <label className="mb-1 block text-xs font-medium text-bodyText">Amount received</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    className="w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
                    value={amountDraft}
                    onChange={(e) => {
                      const next = e.target.value
                      setAmountDraft(formatAmountInput(next))
                      const raw = parseNumericInput(next)
                      if (raw === '' || raw === '.') {
                        onAmountReceivedChange(0)
                        return
                      }
                      const n = Number(raw)
                      if (!Number.isNaN(n)) onAmountReceivedChange(n)
                    }}
                  />
                </div>
                <div className="mt-2 flex justify-between text-sm">
                  <span className="text-bodyText">Change</span>
                  <span className="font-semibold text-green-700">{formatAmountDisplay(change)}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="border-t border-strokeColor p-5">
          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className="w-full rounded-xl bg-s1 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loading ? 'Posting…' : 'Complete sale'}
          </button>
        </div>
      </div>

      {lookupMode && customerListPage ? (
        <RelationLookupModal
          open
          lookupPage={customerListPage}
          targetField={POS_CUSTOMER_LOOKUP_FIELD}
          drillDownFilters={{}}
          autoNew={lookupMode === 'new'}
          returnPath={posReturnPath}
          onClose={() => setLookupMode(null)}
          onConfirm={(_value, record) => {
            void (async () => {
              const customer = await resolveCustomerFromLookup(record, customers)
              if (customer) {
                onCustomerChange(customer)
                void onCustomersRefresh?.()
              }
              setLookupMode(null)
            })()
          }}
        />
      ) : null}
    </div>
  )
}
