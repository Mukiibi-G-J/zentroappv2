import type { Page, PageControlField } from '@/types/page'

/** Frontend-only caption overrides keyed by `sourceTable:fieldName`. */
const CAPTION_OVERRIDES: Record<string, string> = {}

export function getFieldCaption(field: PageControlField, page?: Page): string {
  if (!page) return field.Caption
  const key = `${page.SourceTable}:${field.Name}`
  return CAPTION_OVERRIDES[key] ?? field.Caption
}
