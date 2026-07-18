import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { drillDownKeyValue } from '@/lib/cardAction'

/**
 * Build list filters for a relation lookup page from the parent card/list record.
 * Prefer the opening field's RelationContextField (e.g. Item Journal `item`) over
 * the parent primary key (e.g. document_no), which would empty ItemUnitOfMeasure lists.
 */
export function buildLookupDrillDownFilters(
  lookupPage: Page,
  parentRecord: DataRecord | Record<string, unknown>,
  parentFields: PageControlField[],
  targetField?: PageControlField | null,
): Record<string, string> {
  const filters: Record<string, string> = {}
  const ctxField = (lookupPage.ContextFilterField || '').trim()
  if (!ctxField) return filters

  const preferredKeys: string[] = []
  const relationCtx = (targetField?.RelationContextField || '').trim()
  if (relationCtx) preferredKeys.push(relationCtx)

  if (ctxField === 'item__no' || ctxField.startsWith('item')) {
    preferredKeys.push('item', 'no')
  } else if (ctxField.includes('__')) {
    preferredKeys.push(ctxField.split('__')[0]!)
  } else {
    preferredKeys.push(ctxField)
  }

  const seen = new Set<string>()
  for (const key of preferredKeys) {
    if (!key || seen.has(key)) continue
    seen.add(key)
    const raw = parentRecord[key]
    if (raw !== null && raw !== undefined && raw !== '') {
      filters[ctxField] = String(raw)
      return filters
    }
  }

  // Last resort: primary key / no / code — only when context is not item-scoped
  if (!ctxField.startsWith('item')) {
    const ctxValue = drillDownKeyValue(
      {} as PageControlField,
      parentRecord,
      undefined,
      parentFields,
    )
    if (ctxValue) filters[ctxField] = ctxValue
  }

  return filters
}
