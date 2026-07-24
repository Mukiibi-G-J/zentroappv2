'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Filter, RefreshCw, Search } from 'lucide-react'
import DatePicker from '@/components/ui/DatePicker'
import { cn } from '@/lib/utils'
import { purchasesService } from '@/services/purchases.service'
import {
  buildPostedPurchaseFilterUrl,
  buildPurchaseSummaryParams,
  detectQuickRange,
  formatPurchaseCurrency,
  quickRangeDates,
  type PostedPurchaseHistoryFilters,
  type QuickRangeKey,
} from '@/lib/postedPurchaseHistory'
import { useLocalCurrencyCode } from '@/hooks/useLocalCurrencyCode'

interface Props {
  pageId: number
  filters: PostedPurchaseHistoryFilters
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

export default function PostedPurchaseHistoryPanel({
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
  const [totals, setTotals] = useState({
    total_purchases: 0,
    total_products: 0,
    total_invoices: 0,
  })
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
      buildPostedPurchaseFilterUrl(
        pageId,
        {
          posting_date_from: range.from,
          posting_date_to: range.to,
          filterLabel: 'This month',
        },
        returnUrl,
      ),
    )
  }, [hasDateScope, pageId, returnUrl, router])

  useEffect(() => {
    if (filters.posting_date) {
      setStartDate(filters.posting_date)
      setEndDate(filters.posting_date)
    } else {
      setStartDate(filters.posting_date_from ?? '')
      setEndDate(filters.posting_date_to ?? '')
    }
    setQuickRange(detectQuickRange(filters))
  }, [filters.posting_date, filters.posting_date_from, filters.posting_date_to])

  useEffect(() => {
    let cancelled = false
    const params = buildPurchaseSummaryParams(filters)
    ;(async () => {
      setLoadingSummary(true)
      try {
        const summary = await purchasesService.getPurchaseSummary(params)
        if (cancelled) return
        setTotals({
          total_purchases: summary.total_purchases ?? 0,
          total_products: summary.total_products ?? 0,
          total_invoices: summary.total_invoices ?? 0,
        })
      } catch {
        if (!cancelled) {
          setTotals({ total_purchases: 0, total_products: 0, total_invoices: 0 })
        }
      } finally {
        if (!cancelled) setLoadingSummary(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [filters.posting_date, filters.posting_date_from, filters.posting_date_to])

  const applyFilters = useCallback(
    (overrides?: Partial<PostedPurchaseHistoryFilters & { filterLabel?: string }>) => {
      const from = overrides?.posting_date_from ?? startDate
      const to = overrides?.posting_date_to ?? endDate
      const single = overrides?.posting_date

      const next: PostedPurchaseHistoryFilters & { filterLabel?: string } = {
        filterLabel: overrides?.filterLabel,
      }

      if (single) {
        next.posting_date = single
      } else if (from && to) {
        next.posting_date_from = from
        next.posting_date_to = to
        if (!next.filterLabel) next.filterLabel = 'Custom range'
      }

      router.push(buildPostedPurchaseFilterUrl(pageId, next, returnUrl))
    },
    [startDate, endDate, pageId, returnUrl, router],
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
          label="Purchases"
          value={loadingSummary ? '…' : formatPurchaseCurrency(totals.total_purchases, currencyCode)}
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
      </div>

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
