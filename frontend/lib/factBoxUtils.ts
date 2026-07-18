import type { PageControl } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

const DEFAULT_LINK_FIELDS: Record<string, string> = {
  ItemImages: 'no',
  DocumentAttachment: 'id',
}

function readDataField(data: DataRecord, fieldName: string): unknown {
  if (fieldName in data) return data[fieldName]
  const lower = fieldName.toLowerCase()
  if (lower in data) return data[lower]
  const camel = fieldName.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
  if (camel in data) return data[camel]
  return undefined
}

/** Resolve the parent record key for a fact box from page-engine LinkField metadata. */
export function resolveFactBoxParentKey(control: PageControl, data: DataRecord): string | null {
  const linkField =
    control.LinkField?.trim() ||
    DEFAULT_LINK_FIELDS[control.SourceTable] ||
    null

  if (!linkField) return null

  const value = readDataField(data, linkField)
  if (value == null || value === '') return null
  return String(value)
}
