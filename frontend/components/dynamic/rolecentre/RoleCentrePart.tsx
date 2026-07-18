'use client'

import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { usePages } from '@/hooks/usePage'
import { getCardRecordPath, listDashboardPathByPageId } from '@/lib/pageRoutes'
import type { RoleCentreSection } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

interface Props {
  section: RoleCentreSection
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}

export default function RoleCentrePart({ section }: Props) {
  const router = useRouter()
  const { data: pages = [] } = usePages()

  const partPage = pages.find((p) => p.PageId === section.PartPageId)
  const cardPageId = partPage?.CardPageId ?? null
  const cardPage = cardPageId ? pages.find((p) => p.PageId === cardPageId) : null
  const cardPageType = cardPage?.PageType ?? null

  const rows = section.Rows ?? []
  const columns = rows.length > 0
    ? Object.keys(rows[0]).filter((k) => k !== 'SystemId').slice(0, 6)
    : []

  const handleViewAll = () => {
    if (section.PartPageId) router.push(listDashboardPathByPageId(pages, section.PartPageId))
  }

  const handleRowClick = (record: DataRecord) => {
    if (!cardPageId || !record.SystemId) return
    router.push(getCardRecordPath(cardPageId, record.SystemId, cardPageType))
  }

  return (
    <div className="rounded-xl border border-strokeColor bg-white overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption}</h3>
        {section.PartPageId && (
          <button
            type="button"
            onClick={handleViewAll}
            className="inline-flex items-center gap-1 text-xs font-medium text-s1 hover:opacity-80 transition"
          >
            View All
            <ArrowRight size={13} />
          </button>
        )}
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
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map((record) => {
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
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
