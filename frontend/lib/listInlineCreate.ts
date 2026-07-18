import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

/** Prefill a new inline row from active drill-down filters. */
export function drillDownDefaultsForNewRow(
  fields: PageControlField[],
  filters: Record<string, string>,
): Partial<DataRecord> {
  const defaults: Partial<DataRecord> = {}

  for (const [filterKey, filterValue] of Object.entries(filters)) {
    if (filterValue === null || filterValue === undefined || filterValue === '') continue

    if (fields.some((field) => field.Name === filterKey)) {
      defaults[filterKey] = filterValue
      continue
    }

    const relationField = filterKey.includes('__')
      ? filterKey.split('__').slice(-1)[0]
      : null
    if (
      relationField &&
      fields.some((field) => field.Name === relationField && field.HasTableRelation)
    ) {
      defaults[relationField] = filterValue
    }
  }

  return defaults
}
