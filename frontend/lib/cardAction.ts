import { getCardRecordPath } from '@/lib/pageRoutes'
import type { Page, PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

/** Resolve the source record field used as the drill-down filter value. */
export function drillDownKeyValue(
  _field: PageControlField,
  record: DataRecord | Record<string, unknown>,
  _sourcePage?: Page,
  sourceFields?: PageControlField[],
): string | null {
  const pkField = sourceFields?.find((f) => f.PrimaryKey)?.Name
  const candidates = [pkField, 'email', 'full_name', 'no', 'code'].filter(Boolean) as string[]

  for (const keyField of candidates) {
    const raw = record[keyField]
    if (raw !== null && raw !== undefined && raw !== '') {
      return String(raw)
    }
  }
  return null
}

/** Replace `{fieldName}` placeholders in action URLs from the selected record. */
export function substituteActionUrlPlaceholders(
  actionRelativeUrl: string,
  record: DataRecord | Record<string, unknown>,
  sourceFields: PageControlField[],
): string {
  const pkField = sourceFields.find((f) => f.PrimaryKey)?.Name
  return actionRelativeUrl.replace(/\{(\w+)\}/g, (_match, fieldName: string) => {
    const raw = record[fieldName]
    if (raw !== null && raw !== undefined && raw !== '') {
      return encodeURIComponent(String(raw))
    }
    if (pkField && fieldName === pkField) {
      const pkRaw = record[pkField]
      if (pkRaw !== null && pkRaw !== undefined && pkRaw !== '') {
        return encodeURIComponent(String(pkRaw))
      }
    }
    if (fieldName === 'id') {
      const systemId = record.SystemId
      if (systemId !== null && systemId !== undefined && systemId !== '') {
        return encodeURIComponent(String(systemId))
      }
    }
    return ''
  })
}

/** Resolve a card PageAction target (page name) into a list URL with drill-down context. */
export function buildCardActionUrl(
  basePath: string,
  actionRelativeUrl: string,
  targetPages: Page[],
  record: DataRecord | Record<string, unknown>,
  sourceFields: PageControlField[],
  returnUrl: string,
): string | null {
  const trimmed = substituteActionUrlPlaceholders(
    (actionRelativeUrl || '').trim(),
    record,
    sourceFields,
  )
  if (!trimmed) return null

  const [pageName, queryString] = trimmed.split('?', 2)
  const targetPage = targetPages.find((p) => p.Name === pageName)
  if (!targetPage) return null

  const extraParams = new URLSearchParams()
  if (queryString) {
    for (const part of queryString.split('&')) {
      const [key, value] = part.split('=')
      if (!key || value === undefined) continue
      if (key === 'applied_to_entry_id' && !value) return null
      if (key === 'vendor_ledger_entry_id' && !value) return null
      if (key === 'customer_ledger_entry_id' && !value) return null
      extraParams.set(key, decodeURIComponent(value))
    }
  }

  const needsContext = Boolean((targetPage.ContextFilterField || '').trim())
  let keyValue: string | null = null
  if (needsContext || extraParams.get('mode') === 'new') {
    keyValue = drillDownKeyValue(
      {} as PageControlField,
      record,
      undefined,
      sourceFields,
    )
    if (needsContext && !keyValue) return null
  }

  // Open a new card for this related record (e.g. Bring in Opening Balance → 10204).
  if (
    extraParams.get('mode') === 'new' &&
    targetPage.CardPageId &&
    targetPage.InsertAllowed !== false
  ) {
    if (!keyValue) return null
    const query: Record<string, string> = {
      fromList: String(targetPage.ObjectId ?? targetPage.PageId),
      ctx: keyValue,
      return: returnUrl,
    }
    const label = record.full_name ?? record.name ?? record.item_name ?? record.description
    if (label) query.ctxLabel = String(label)
    return getCardRecordPath(targetPage.CardPageId, 'new', 'Card', query)
  }

  const params = new URLSearchParams()
  params.set('page', String(targetPage.PageId))
  params.set('return', returnUrl)

  if (needsContext && keyValue) {
    params.set('ctx', keyValue)
    const label = record.full_name ?? record.name ?? record.item_name ?? record.description
    if (label) params.set('ctxLabel', String(label))
  }

  for (const [key, value] of extraParams.entries()) {
    if (key === 'mode') continue
    params.set(key, value)
  }

  return `${basePath}?${params.toString()}`
}

/** Line ribbon actions that navigate to another page (not #apply-* tokens). */
export function isLineNavigateAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  if (!url || url.startsWith('#')) return false
  return true
}

/** Open a card/document or drill-down list from a subform line action. */
export function buildLineNavigateHref(
  action: PageAction,
  line: DataRecord,
  allPages: Pick<Page, 'PageId' | 'Name' | 'PageType' | 'ContextFilterField'>[],
  sourceFields: PageControlField[],
  returnUrl?: string,
): string | null {
  const trimmed = substituteActionUrlPlaceholders(
    (action.ActionRelativeUrl || '').trim(),
    line,
    sourceFields,
  )
  if (!trimmed) return null

  const [pageName, queryString] = trimmed.split('?', 2)
  const targetPage = allPages.find((p) => p.Name === pageName)
  if (!targetPage) return null

  if (targetPage.PageType === 'Card' || targetPage.PageType === 'Document') {
    const systemId = String(line.SystemId ?? '').trim()
    if (!systemId) return null
    const query: Record<string, string> = {}
    if (returnUrl) query.return = returnUrl
    if (queryString) {
      for (const part of queryString.split('&')) {
        const [key, value] = part.split('=')
        if (!key || value === undefined) continue
        query[key] = decodeURIComponent(value)
      }
    }
    return getCardRecordPath(targetPage.PageId, systemId, targetPage.PageType, query)
  }

  return buildCardActionUrl(
    '/dashboard',
    trimmed,
    allPages as Page[],
    line,
    sourceFields,
    returnUrl ?? '/dashboard',
  )
}
