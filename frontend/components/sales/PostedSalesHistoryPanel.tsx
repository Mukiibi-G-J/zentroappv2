'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronDown, ChevronUp, Filter, RefreshCw, Search } from 'lucide-react'
import DatePicker from '@/components/ui/DatePicker'
import { cn } from '@/lib/utils'
import { salesService } from '@/services/sales.service'
import {
  buildPostedSalesFilterUrl,
  buildSalesSummaryParams,
  detectQuickRange,
  formatSalesCurrency,
  quickRangeDates,
  type PostedSalesHistoryFilters,
  type QuickRangeKey,
  type SalesUserSummaryRow,
} from '@/lib/postedSalesHistory'
import { useLocalCurrencyCode } from '@/hooks/useLocalCurrencyCode'

interface Props {
  pageId: number
  filters: PostedSalesHistoryFilters
  returnUrl?: string | null
  search: string
  onSearchChange: (value: string) => void
}

const QUICK_RANGE_OPTIONS: { value: QuickRangeKey; label: string }[] = [
  { value: 'all_posted', label: 'All posted' },
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'this_week', label: 'This week' },
  { value: 'this_month', label: 'This month' },
  { value: 'this_quarter', label: 'This quarter' },
]

export default function PostedSalesHistoryPanel({
  pageId,
  filters,
  returnUrl,
  search,
  onSearchChange,
}: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const currencyCode = useLocalCurrencyCode()

  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [quickRange, setQuickRange] = useState<QuickRangeKey>('this_month')
  const [paymentMethod, setPaymentMethod] = useState('')
  const [paymentMethods, setPaymentMethods] = useState<
    Array<{ id: number; code: string; description: string }>
  >([])
  const [showUserBreakdown, setShowUserBreakdown] = useState(false)
  const [totals, setTotals] = useState({ total_sales: 0, total_products: 0, total_invoices: 0 })
  const [userSummaries, setUserSummaries] = useState<SalesUserSummaryRow[]>([])
  const [loadingSummary, setLoadingSummary] = useState(true)
  const didAutoApplyDefault = useRef(false)

  const hasDateScope = Boolean(
    searchParams.get('posting_date')
    || searchParams.get('posting_date_from')
    || searchParams.get('posting_date_to'),
  )

  useEffect(() => {
    if (didAutoApplyDefault.current || hasDateScope) return
    didAutoApplyDefault.current = true
    const range = quickRangeDates('this_month')
    if (!range) return
    router.replace(
      buildPostedSalesFilterUrl(
        pageId,
        {
          posting_date_from: range.from,
          posting_date_to: range.to,
          filterLabel: 'This month',
          ledger_user_id: filters.ledger_user_id,
        },
        returnUrl,
      ),
    )
  }, [filters.ledger_user_id, hasDateScope, pageId, returnUrl, router])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const methods = await salesService.getPaymentMethods()
        if (!cancelled) setPaymentMethods(methods)
      } catch {
        if (!cancelled) setPaymentMethods([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (filters.posting_date) {
      setStartDate(filters.posting_date)
      setEndDate(filters.posting_date)
    } else {
      setStartDate(filters.posting_date_from ?? '')
      setEndDate(filters.posting_date_to ?? '')
    }
    setPaymentMethod(filters.payment_method ?? '')
    setQuickRange(detectQuickRange(filters))
  }, [filters.posting_date, filters.posting_date_from, filters.posting_date_to, filters.payment_method])

  useEffect(() => {
    let cancelled = false
    const params = buildSalesSummaryParams(filters)
    ;(async () => {
      setLoadingSummary(true)
      try {
        const [summary, userData] = await Promise.all([
          salesService.getSalesSummary(params),
          salesService.getSalesUserSummary(params),
        ])
        if (cancelled) return
        setTotals({
          total_sales: summary.total_sales ?? 0,
          total_products: summary.total_products ?? 0,
          total_invoices: summary.total_invoices ?? 0,
        })
        setUserSummaries(
          (userData.users ?? []).map((u) => ({
            user_id: u.user_id,
            user_name: u.user_name,
            total_sales: u.total_sales ?? 0,
            total_products: u.total_products ?? 0,
            total_invoices: u.total_invoices ?? 0,
          })),
        )
      } catch {
        if (!cancelled) {
          setTotals({ total_sales: 0, total_products: 0, total_invoices: 0 })
          setUserSummaries([])
        }
      } finally {
        if (!cancelled) setLoadingSummary(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [
    filters.posting_date,
    filters.posting_date_from,
    filters.posting_date_to,
    filters.payment_method,
    filters.ledger_user_id,
  ])

  const applyFilters = useCallback(
    (overrides?: Partial<PostedSalesHistoryFilters & { filterLabel?: string }>) => {
      const from = overrides?.posting_date_from ?? startDate
      const to = overrides?.posting_date_to ?? endDate
      const single = overrides?.posting_date
      const pm = overrides?.payment_method ?? paymentMethod

      const next: PostedSalesHistoryFilters & { filterLabel?: string } = {
        ledger_user_id: filters.ledger_user_id,
        payment_method: pm || undefined,
        filterLabel: overrides?.filterLabel,
      }

      if (single) {
        next.posting_date = single
      } else if (from && to) {
        next.posting_date_from = from
        next.posting_date_to = to
        if (!next.filterLabel) next.filterLabel = 'Custom range'
      }

      router.push(buildPostedSalesFilterUrl(pageId, next, returnUrl))
    },
    [startDate, endDate, paymentMethod, pageId, returnUrl, router, filters.ledger_user_id],
  )

  const handleReset = useCallback(() => {
    const params = new URLSearchParams()
    params.set('page', String(pageId))
    if (returnUrl) params.set('return', returnUrl)
    router.push(`/dashboard?${params.toString()}`)
  }, [pageId, returnUrl, router])

  const handleQuickRangeChange = (value: QuickRangeKey) => {
    setQuickRange(value)
    if (!value) return

    if (value === 'all_posted') {
      handleReset()
      return
    }

    const range = quickRangeDates(value)
    if (!range) return
    setStartDate(range.from)
    setEndDate(range.to)
    const label = QUICK_RANGE_OPTIONS.find((o) => o.value === value)?.label
    if (value === 'today' || value === 'yesterday') {
      applyFilters({
        posting_date: range.from,
        filterLabel: label,
      })
    } else {
      applyFilters({
        posting_date_from: range.from,
        posting_date_to: range.to,
        filterLabel: label,
      })
    }
  }

  return (
    <div className="shrink-0 rounded-lg border border-strokeColor bg-white">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-gray-100">
        <StatPill
          label="Sales"
          value={loadingSummary ? '…' : formatSalesCurrency(totals.total_sales, currencyCode)}
          tone="green"
        />
        <StatPill
          label="Units"
          value={loadingSummary ? '…' : totals.total_products.toLocaleString()}
          tone="blue"
        />
        <StatPill
          label="Invoices"
          value={loadingSummary ? '…' : totals.total_invoices.toLocaleString()}
          tone="neutral"
        />
        <button
          type="button"
          onClick={() => setShowUserBreakdown((v) => !v)}
          className="ml-auto flex items-center gap-1 text-xs font-medium text-s1 hover:underline"
        >
          Sales by user ({userSummaries.length})
          {showUserBreakdown ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {showUserBreakdown && (
        <div className="max-h-36 overflow-auto border-b border-gray-100">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium text-bodyText">User</th>
                <th className="px-3 py-1.5 text-right font-medium text-bodyText">Sales</th>
                <th className="px-3 py-1.5 text-right font-medium text-bodyText">Invoices</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {userSummaries.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-3 py-3 text-center text-bodyText">
                    {loadingSummary ? 'Loading…' : 'No data for this range'}
                  </td>
                </tr>
              ) : (
                userSummaries.map((row, i) => (
                  <tr key={`${row.user_id ?? 'u'}-${i}`}>
                    <td className="px-3 py-1.5 text-mainTextColor">{row.user_name}</td>
                    <td className="px-3 py-1.5 text-right font-medium">{formatSalesCurrency(row.total_sales, currencyCode)}</td>
                    <td className="px-3 py-1.5 text-right text-bodyText">{row.total_invoices}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <div className="flex items-center gap-1.5 min-w-[200px]">
          <DatePicker
            value={startDate}
            onChange={(v) => {
              setStartDate(v)
              setQuickRange('')
            }}
            placeholder="From"
            className="text-xs"
          />
          <span className="text-xs text-bodyText">–</span>
          <DatePicker
            value={endDate}
            onChange={(v) => {
              setEndDate(v)
              setQuickRange('')
            }}
            placeholder="To"
            className="text-xs"
          />
        </div>

        <select
          value={quickRange}
          onChange={(e) => handleQuickRangeChange(e.target.value as QuickRangeKey)}
          className="h-9 px-2 text-xs border border-strokeColor rounded-lg bg-white text-mainTextColor min-w-[130px]"
        >
          <option value="" disabled>
            Quick range
          </option>
          {QUICK_RANGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          value={paymentMethod}
          onChange={(e) => setPaymentMethod(e.target.value)}
          className="h-9 px-2 text-xs border border-strokeColor rounded-lg bg-white text-mainTextColor max-w-[160px]"
        >
          <option value="">All payments</option>
          {paymentMethods.map((m) => (
            <option key={m.id} value={String(m.id)}>
              {m.code}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => applyFilters()}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium bg-s1 text-white rounded-lg hover:opacity-90"
        >
          <Filter size={12} />
          Apply
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs border border-strokeColor rounded-lg hover:bg-gray-50 text-bodyText"
        >
          <RefreshCw size={12} />
          Reset
        </button>

        <div className="relative flex-1 min-w-[140px] max-w-xs ml-auto">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-bodyText" />
          <input
            className="w-full pl-8 pr-2 py-1.5 text-xs border border-strokeColor rounded-lg focus:outline-none focus:ring-2 focus:ring-s1/30"
            placeholder="Search invoices…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
      </div>
    </div>
  )
}

function StatPill({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'green' | 'blue' | 'neutral'
}) {
  const tones = {
    green: 'bg-green-50 text-green-700 border-green-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    neutral: 'bg-gray-50 text-mainTextColor border-gray-200',
  }
  return (
    <div className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs', tones[tone])}>
      <span className="font-medium opacity-70">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  )
}
