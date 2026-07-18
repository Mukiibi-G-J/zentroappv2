'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import SearchableRelationSelect from '@/components/dynamic/SearchableRelationSelect'
import RelationLookupModal from '@/components/dynamic/RelationLookupModal'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { PaymentJournalReceiptDialog } from '@/components/payments/PaymentJournalReceiptDialog'
import { usePages } from '@/hooks/usePage'
import { formatAmountInput, formatDecimalDisplay, parseNumericInput } from '@/lib/formatNumber'
import { PAGE_IDS } from '@/lib/pageIds'
import { quickCustomerPayment } from '@/services/payments.service'
import { salesService } from '@/services/sales.service'
import type { RelationOption } from '@/hooks/useRelationOptions'
import type { RelationMenuFooter } from '@/lib/relationMenuFooter'
import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import type { POSCustomer, POSPaymentMethod } from '@/types/pos'

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
  const balance = Number(c.balance ?? 0)
  const balanceLabel =
    balance > 0 ? ` · ${formatDecimalDisplay(balance)} due` : ''
  return {
    value: String(c.id),
    label: `${c.name} (${c.no})${balanceLabel}`,
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
      balance:
        record.balance != null && record.balance !== ''
          ? Number(record.balance)
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

function pickDefaultMethod(
  methods: POSPaymentMethod[],
  customer: POSCustomer | null,
): POSPaymentMethod | null {
  if (customer?.payment_method && methods.length) {
    const preferred = methods.find((m) => m.id === customer.payment_method)
    if (preferred) return preferred
  }
  return (
    methods.find((m) => m.code.toUpperCase() === 'CASH') ??
    methods.find((m) => m.requires_amount_received) ??
    methods[0] ??
    null
  )
}

interface POSRecordPaymentDialogProps {
  open: boolean
  customers: POSCustomer[]
  paymentMethods: POSPaymentMethod[]
  onCustomersRefresh?: () => void | Promise<void>
  onClose: () => void
  onSuccess?: () => void
}

export function POSRecordPaymentDialog({
  open,
  customers,
  paymentMethods,
  onCustomersRefresh,
  onClose,
  onSuccess,
}: POSRecordPaymentDialogProps) {
  const [selectedCustomer, setSelectedCustomer] = useState<POSCustomer | null>(null)
  const [selectedMethod, setSelectedMethod] = useState<POSPaymentMethod | null>(null)
  const [amountDraft, setAmountDraft] = useState('')
  const [lookupMode, setLookupMode] = useState<'list' | 'new' | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [receiptSystemId, setReceiptSystemId] = useState<string | null>(null)

  const { data: allPages = [] } = usePages()
  const customerListPage = useMemo(
    () =>
      allPages.find((p) => p.Name === 'CustomerList') ??
      allPages.find((p) => p.PageId === PAGE_IDS.CUSTOMERS),
    [allPages],
  )

  const debtorCustomers = useMemo(() => {
    const nonGeneral = customers.filter((c) => {
      if (c.customer_type === 'General') return false
      const name = c.name.toLowerCase()
      return !(
        name.includes('general') ||
        name.includes('walk-in') ||
        name.includes('cash customer')
      )
    })
    const withBalance = nonGeneral.filter((c) => Number(c.balance ?? 0) > 0)
    return withBalance.length > 0 ? withBalance : nonGeneral
  }, [customers])

  useEffect(() => {
    if (!open) return
    const firstDebtor =
      debtorCustomers.find((c) => Number(c.balance ?? 0) > 0) ??
      debtorCustomers[0] ??
      null
    setSelectedCustomer(firstDebtor)
    setSelectedMethod(pickDefaultMethod(paymentMethods, firstDebtor))
    setAmountDraft(
      firstDebtor && Number(firstDebtor.balance ?? 0) > 0
        ? formatDecimalDisplay(Number(firstDebtor.balance))
        : '',
    )
    setLookupMode(null)
    setLoading(false)
  }, [open, debtorCustomers, paymentMethods])

  const customerOptions = useMemo(() => {
    const opts = debtorCustomers.map(customerToOption)
    if (
      selectedCustomer &&
      !opts.some((o) => o.value === String(selectedCustomer.id))
    ) {
      opts.unshift(customerToOption(selectedCustomer))
    }
    return opts
  }, [debtorCustomers, selectedCustomer])

  const customerMenuFooter = useMemo((): RelationMenuFooter | undefined => {
    if (!customerListPage) return undefined
    return {
      onNew: () => setLookupMode('new'),
      onSelectFromFullList: () => setLookupMode('list'),
    }
  }, [customerListPage])

  if (!open) return null

  const outstanding = Number(selectedCustomer?.balance ?? 0)
  const amountPaid = Number(parseNumericInput(amountDraft) || 0)

  const handleCustomerChange = (customer: POSCustomer) => {
    setSelectedCustomer(customer)
    setSelectedMethod(pickDefaultMethod(paymentMethods, customer))
    if (Number(customer.balance ?? 0) > 0) {
      setAmountDraft(formatDecimalDisplay(Number(customer.balance)))
    }
  }

  const validateForm = () => {
    if (!selectedCustomer) {
      toast.error('Select a customer')
      return false
    }
    if (!selectedMethod) {
      toast.error('Select a payment method')
      return false
    }
    if (!(amountPaid > 0)) {
      toast.error('Enter an amount greater than zero')
      return false
    }
    return true
  }

  const handlePost = async () => {
    if (!validateForm() || !selectedCustomer || !selectedMethod) return
    setLoading(true)
    try {
      const result = await quickCustomerPayment({
        customer_id: selectedCustomer.id,
        amount: Math.round(amountPaid),
        payment_method_id: selectedMethod.id,
      })
      toast.success(
        `Payment ${result.document_no} posted` +
          (result.applied_document_no
            ? ` — applied to ${result.applied_document_no}`
            : ''),
      )
      if (result.system_id) {
        setReceiptSystemId(result.system_id)
        void onCustomersRefresh?.()
        return
      }
      void onCustomersRefresh?.()
      onSuccess?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to record payment')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <h2 className="text-lg font-semibold text-mainTextColor">Record payment</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-bodyText hover:text-mainTextColor"
          >
            Close
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">Customer</label>
            <SearchableRelationSelect
              options={customerOptions}
              value={selectedCustomer ? String(selectedCustomer.id) : ''}
              placeholder="Search debtor…"
              menuFooter={customerMenuFooter}
              onChange={(value) => {
                const c =
                  debtorCustomers.find((x) => String(x.id) === value) ??
                  customers.find((x) => String(x.id) === value) ??
                  (selectedCustomer && String(selectedCustomer.id) === value
                    ? selectedCustomer
                    : null)
                if (c) handleCustomerChange(c)
              }}
              noOptionsMessage="No customers found"
            />
            {selectedCustomer ? (
              <p className="mt-1.5 text-xs text-bodyText">
                Outstanding:{' '}
                <span className="font-semibold text-mainTextColor">
                  {formatDecimalDisplay(outstanding)}
                </span>
              </p>
            ) : null}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">
              Amount paid
            </label>
            <input
              type="text"
              inputMode="decimal"
              className="w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
              value={amountDraft}
              onChange={(e) => setAmountDraft(formatAmountInput(e.target.value))}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-bodyText">
              Payment method
            </label>
            <select
              className="w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
              value={selectedMethod?.id ?? ''}
              onChange={(e) => {
                const m = paymentMethods.find((x) => x.id === Number(e.target.value))
                if (m) setSelectedMethod(m)
              }}
            >
              {paymentMethods.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.description || m.code}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="border-t border-strokeColor p-5">
          <button
            type="button"
            disabled={loading}
            onClick={() => {
              if (!validateForm()) return
              setConfirmOpen(true)
            }}
            className="w-full rounded-xl bg-s1 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loading ? 'Posting…' : 'Post payment'}
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
          onClose={() => setLookupMode(null)}
          onConfirm={(_value, record) => {
            void (async () => {
              const customer = await resolveCustomerFromLookup(record, customers)
              if (customer) {
                handleCustomerChange(customer)
                void onCustomersRefresh?.()
              }
              setLookupMode(null)
            })()
          }}
        />
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        title="Post payment"
        message="Are you sure you want to post this payment? A receipt will be shown after posting."
        confirmLabel="Post payment"
        onConfirm={() => {
          setConfirmOpen(false)
          void handlePost()
        }}
        onCancel={() => setConfirmOpen(false)}
      />

      <PaymentJournalReceiptDialog
        open={receiptSystemId != null}
        systemId={receiptSystemId}
        onClose={() => {
          setReceiptSystemId(null)
          onSuccess?.()
          onClose()
        }}
      />
    </div>
  )
}
