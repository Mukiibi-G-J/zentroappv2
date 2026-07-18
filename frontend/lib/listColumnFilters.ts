import type { PageControlField } from '@/types/page'

/** URL prefix for column filters (browser URL only; API uses plain field names). */
export const COLUMN_FILTER_PREFIX = 'cf_'
export const LIST_SORT_PARAM = 'sort'
export const LIST_ORDER_PARAM = 'order'

export type ListSortOrder = 'asc' | 'desc'

export interface ListColumnSort {
  field: string
  order: ListSortOrder
}

export function columnFilterParamKey(fieldName: string): string {
  return `${COLUMN_FILTER_PREFIX}${fieldName}`
}

export function parseColumnFilters(searchParams: URLSearchParams): Record<string, string> {
  const result: Record<string, string> = {}
  searchParams.forEach((value, key) => {
    if (!key.startsWith(COLUMN_FILTER_PREFIX) || !value) return
    const field = key.slice(COLUMN_FILTER_PREFIX.length)
    if (field) result[field] = value
  })
  return result
}

export function parseListSort(searchParams: URLSearchParams): ListColumnSort | null {
  const field = searchParams.get(LIST_SORT_PARAM)?.trim()
  if (!field) return null
  const orderRaw = (searchParams.get(LIST_ORDER_PARAM) || 'asc').toLowerCase()
  const order: ListSortOrder = orderRaw === 'desc' ? 'desc' : 'asc'
  return { field, order }
}

export function serializeFilterValue(field: PageControlField, value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  if (field.FieldType === 'Boolean') return value ? 'true' : 'false'
  if (field.FieldType === 'Date' && value) {
    try {
      return new Date(String(value)).toISOString().slice(0, 10)
    } catch {
      return String(value)
    }
  }
  if (field.FieldType === 'Code') return String(value).toUpperCase()
  return String(value)
}

export function formatColumnFilterLabel(field: PageControlField, value: string): string {
  if (field.FieldType === 'Boolean') {
    return value === 'true' ? 'Yes' : value === 'false' ? 'No' : value
  }
  return value
}
