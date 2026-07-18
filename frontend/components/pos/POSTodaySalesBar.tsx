'use client'

import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { ReturnTypeUseSalesPOS } from '@/components/pos/posTypes'

interface POSTodaySalesBarProps {
  pos: ReturnTypeUseSalesPOS
}

export function POSTodaySalesBar({ pos }: POSTodaySalesBarProps) {
  const { showTodayMySales, setShowTodayMySales, todayMySales, loadingTodayMySales } = pos

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
      <button
        type="button"
        onClick={() => setShowTodayMySales((prev) => !prev)}
        className="inline-flex items-center rounded-lg border border-strokeColor bg-white px-3 py-1.5 text-xs font-medium text-bodyText transition hover:bg-softBg sm:text-sm"
        title={showTodayMySales ? 'Hide amount' : 'Show amount'}
      >
        {showTodayMySales ? 'Hide my sales' : 'Show my sales'}
      </button>
      <div
        className="inline-flex items-center rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5"
        title="Total posted sales you made today"
      >
        <span className="text-xs font-semibold text-emerald-900 sm:text-sm">
          Today my sales:{' '}
          {!showTodayMySales
            ? 'Hidden'
            : loadingTodayMySales
              ? 'Loading…'
              : formatDecimalDisplay(todayMySales)}
        </span>
      </div>
    </div>
  )
}
