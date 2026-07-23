'use client'

import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { usePages } from '@/hooks/usePage'
import { buildDrillDownUrl, drillDownKeyValue, formatDrillDownValue } from '@/lib/drillDown'
import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

interface Props {
  field: PageControlField
  value: unknown
  record: DataRecord | Record<string, unknown>
  sourcePage?: Page
  sourceFields?: PageControlField[]
  basePath?: string
  sourcePageId?: number
  sourceSystemId?: string
  returnPath?: string
  className?: string
}

export default function DrillDownField({
  field,
  value,
  record,
  sourcePage,
  sourceFields,
  basePath = '/dashboard',
  sourcePageId,
  sourceSystemId,
  returnPath,
  className,
}: Props) {
  const router = useRouter()
  const { data: allPages = [] } = usePages()
  const targetPage = allPages.find((p) => p.PageId === field.DrillDownPageId)
  const href = buildDrillDownUrl(
    basePath,
    field,
    record,
    sourcePage,
    sourceFields,
    { sourcePageId, sourceSystemId, returnPath, targetPage },
  )
  const display = formatDrillDownValue(value, field)
  const drillKey = drillDownKeyValue(field, record, sourcePage, sourceFields)
  const itemType = String((record as Record<string, unknown>)?.type ?? '')
    .trim()
    .toLowerCase()
  const isNonStockInventory =
    field.Name === 'inventory' &&
    (itemType === 'service' || itemType === 'non-inventory')
  const isSalesPersonDrillDown =
    targetPage?.Name === 'PostedSalesInvoiceList' &&
    sourcePage?.SourceTable === 'CustomUser' &&
    record.id != null &&
    record.id !== ''
  const isDetailedLedgerDrillDown =
    (targetPage?.Name === 'DetailedCustomerLedgerEntryList' ||
      targetPage?.Name === 'DetailedVendorLedgerEntryList') &&
    record.id != null &&
    record.id !== ''
  const canDrillDown =
    !isNonStockInventory &&
    field.HasDrillDownPage &&
    href &&
    (drillKey !== null || isSalesPersonDrillDown || isDetailedLedgerDrillDown)

  if (!canDrillDown) {
    return (
      <span className={cn('text-mainTextColor tabular-nums', className)}>
        {isNonStockInventory ? '—' : display}
      </span>
    )
  }

  return (
    <button
      type="button"
      onClick={() => router.push(href)}
      className={cn(
        'text-left tabular-nums font-medium text-s1 underline decoration-s1/40 underline-offset-2',
        'hover:decoration-s1 focus:outline-none focus:ring-2 focus:ring-s1/30 rounded',
        className,
      )}
      title={`View ${field.Caption} details`}
    >
      {display}
    </button>
  )
}
