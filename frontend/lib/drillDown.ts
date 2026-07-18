import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { getCardRecordPath, getPageRouteId } from '@/lib/pageRoutes'

/** Resolve the source record field used as the drill-down filter value. */
export function drillDownKeyValue(
  _field: PageControlField,
  record: DataRecord | Record<string, unknown>,
  _sourcePage?: Page,
  sourceFields?: PageControlField[],
): string | null {
  const pkField = sourceFields?.find((f) => f.PrimaryKey)?.Name
  const candidates = [pkField, 'full_name', 'email', 'no', 'code'].filter(Boolean) as string[]

  for (const keyField of candidates) {
    const raw = record[keyField]
    if (raw !== null && raw !== undefined && raw !== '') {
      return String(raw)
    }
  }
  return null
}

export function buildDrillDownUrl(
  basePath: string,
  field: PageControlField,
  record: DataRecord | Record<string, unknown>,
  sourcePage?: Page,
  sourceFields?: PageControlField[],
  options?: {
    sourcePageId?: number
    sourceSystemId?: string
    returnPath?: string
    targetPage?: Page
  },
): string | null {
  if (!field.HasDrillDownPage || !field.DrillDownPageId) return null

  const targetPage = options?.targetPage
  const isSalesPersonDrillDown =
    targetPage?.Name === 'PostedSalesInvoiceList' &&
    sourcePage?.SourceTable === 'CustomUser' &&
    record.id != null &&
    record.id !== ''

  const keyValue = drillDownKeyValue(field, record, sourcePage, sourceFields)
  if (!isSalesPersonDrillDown && !keyValue) return null

  // Document pages (Purchase/Sales invoices, etc.) open on /document/…, not dashboard list.
  if (targetPage?.PageType === 'Document') {
    const systemId = record.SystemId ?? record.system_id
    if (!systemId) return null
    const query: Record<string, string> = {}
    if (sourcePage) {
      query.fromList = String(getPageRouteId(sourcePage))
    }
    if (options?.returnPath) {
      query.return = options.returnPath
    }
    return getCardRecordPath(targetPage.PageId, String(systemId), 'Document', query)
  }

  const params = new URLSearchParams()
  const routePageId = targetPage ? getPageRouteId(targetPage) : field.DrillDownPageId
  params.set('page', String(routePageId))

  if (isSalesPersonDrillDown) {
    params.set('ctx2Field', 'ledger_user_id')
    params.set('ctx2', String(record.id))
    const label = record.full_name ?? record.username ?? record.email
    if (label) params.set('ctxLabel', String(label))
    params.set('filterLabel', `Sales by ${label ?? 'user'}`)
  } else {
    params.set('ctx', keyValue!)
    const label = record.name ?? record.item_name ?? record.full_name ?? record.description
    if (label) params.set('ctxLabel', String(label))
  }

  if (options?.returnPath) {
    params.set('return', options.returnPath)
  } else if (options?.sourcePageId && options?.sourceSystemId) {
    params.set('return', `/record/${options.sourcePageId}/${options.sourceSystemId}`)
  }

  return `${basePath}?${params.toString()}`
}

export function formatDrillDownValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Decimal') {
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  }
  if (field.FieldType === 'Integer') {
    return Number(value).toLocaleString()
  }
  return String(value)
}
