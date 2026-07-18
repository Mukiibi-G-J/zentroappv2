'use client'

import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { usePages } from '@/hooks/usePage'
import { getCardRecordPath, listDashboardPathByPageId } from '@/lib/pageRoutes'
import { cn } from '@/lib/utils'
import type { DataRecord } from '@/types/pagedata'
import type { ChartPoint, RoleCentreSection } from '@/types/page'

interface Props {
  section: RoleCentreSection
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}

function statusPillClass(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized.includes('complete')) return 'bg-emerald-100 text-emerald-800'
  if (normalized.includes('partial')) return 'bg-amber-100 text-amber-800'
  if (normalized.includes('open')) return 'bg-sky-100 text-sky-800'
  return 'bg-gray-100 text-gray-700'
}

function formatCompactCurrency(value: number): string {
  if (value >= 1_000_000) return `UGX ${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `UGX ${Math.round(value / 1_000)}K`
  return `UGX ${value.toLocaleString()}`
}

function RevenueChart({
  points,
  totalFormatted,
}: {
  points: ChartPoint[]
  totalFormatted?: string
}) {
  const max = Math.max(...points.map((p) => p.Value), 0)
  if (max <= 0) {
    return (
      <p className="text-sm text-bodyText py-10 text-center leading-relaxed">
        No posted sales invoices in the last 6 months.
        <br />
        <span className="text-xs">Post a sales invoice to see revenue here.</span>
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {totalFormatted ? (
        <p className="text-xs text-bodyText">
          6-month total: <span className="font-semibold text-mainTextColor">{totalFormatted}</span>
        </p>
      ) : null}

      <div className="flex gap-3">
        <div className="flex flex-col justify-between py-1 text-[10px] text-bodyText shrink-0 w-14 text-right">
          <span>{formatCompactCurrency(max)}</span>
          <span>UGX 0</span>
        </div>

        <div className="flex flex-1 items-end gap-2 min-h-[9rem] border-l border-b border-gray-100 pl-2 pb-1">
          {points.map((point) => {
            const height = point.Value > 0 ? Math.max(6, Math.round((point.Value / max) * 100)) : 0
            const amountLabel = point.FormattedValue ?? formatCompactCurrency(point.Value)
            const barKey = `${point.Year ?? point.Label}-${point.Month ?? point.Label}`

            return (
              <div key={barKey} className="flex flex-1 flex-col items-center gap-1 min-w-0">
                <span
                  className={cn(
                    'text-[10px] font-medium tabular-nums text-center leading-tight min-h-[2rem] flex items-end justify-center',
                    point.Value > 0 ? 'text-mainTextColor' : 'text-bodyText',
                  )}
                >
                  {point.Value > 0 ? amountLabel : '—'}
                </span>
                <div className="w-full flex items-end justify-center h-24">
                  {height > 0 ? (
                    <div
                      className="w-full max-w-[2.25rem] rounded-t-md bg-s1 hover:bg-s1/90 transition"
                      style={{ height: `${height}%` }}
                      title={`${point.Label}: ${amountLabel}`}
                    />
                  ) : (
                    <div className="w-full max-w-[2.25rem] h-0.5 rounded bg-gray-200" title={`${point.Label}: no revenue`} />
                  )}
                </div>
                <span className="text-[10px] text-bodyText truncate w-full text-center">{point.Label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function AssistanceSection({ section }: Props) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const rows = section.Rows ?? []
  const chartPoints = section.ChartPoints ?? []

  const partPage = section.PartPageId ? pages.find((p) => p.PageId === section.PartPageId) : null
  const cardPageId = partPage?.CardPageId ?? null
  const cardPage = cardPageId ? pages.find((p) => p.PageId === cardPageId) : null

  const columns = rows.length > 0
    ? Object.keys(rows[0]).filter((k) => k !== 'SystemId' && k.toLowerCase() !== 'status').slice(0, 4)
    : []

  const handleViewAll = () => {
    if (section.PartPageId) router.push(listDashboardPathByPageId(pages, section.PartPageId))
  }

  const handleRowClick = (record: DataRecord) => {
    if (!cardPageId || !record.SystemId) return
    router.push(getCardRecordPath(cardPageId, record.SystemId, cardPage?.PageType ?? null))
  }

  return (
    <div className="space-y-4">
      <div className="border-b border-strokeColor pb-2">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption}</h3>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-strokeColor bg-white p-5">
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-mainTextColor">
              {section.ChartCaption ?? 'Revenue by month'}
            </h4>
            {section.ChartSubtitle ? (
              <p className="text-xs text-bodyText mt-1">{section.ChartSubtitle}</p>
            ) : null}
          </div>
          <RevenueChart
            points={chartPoints}
            totalFormatted={section.ChartTotalFormatted}
          />
        </div>

        <div className="rounded-xl border border-strokeColor bg-white overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h4 className="text-sm font-semibold text-mainTextColor">
              {section.ListCaption ?? 'Recent Sales Orders'}
            </h4>
            {section.PartPageId ? (
              <button
                type="button"
                onClick={handleViewAll}
                className="inline-flex items-center gap-1 text-xs font-medium text-s1 hover:opacity-80 transition"
              >
                View All
                <ArrowRight size={13} />
              </button>
            ) : null}
          </div>

          {rows.length === 0 ? (
            <p className="px-5 py-8 text-sm text-bodyText text-center">No records</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="px-4 py-2.5 text-left text-xs font-medium text-bodyText uppercase tracking-wide whitespace-nowrap"
                      >
                        {col.replace(/_/g, ' ')}
                      </th>
                    ))}
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-bodyText uppercase tracking-wide">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {rows.map((record) => {
                    const status = String(record.status ?? record.Status ?? '')
                    const canNavigate = Boolean(cardPageId && record.SystemId)
                    return (
                      <tr
                        key={record.SystemId}
                        onClick={() => handleRowClick(record)}
                        className={canNavigate ? 'cursor-pointer hover:bg-softBg transition' : undefined}
                      >
                        {columns.map((col) => (
                          <td key={col} className="px-4 py-2.5 text-mainTextColor whitespace-nowrap">
                            {formatCellValue(record[col])}
                          </td>
                        ))}
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          {status ? (
                            <span
                              className={cn(
                                'inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium',
                                statusPillClass(status),
                              )}
                            >
                              {status}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
