import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

/** Value to write on the parent field when a lookup row is confirmed. */
export function relationValueFromRecord(
  targetField: PageControlField,
  listRecord: DataRecord,
): string {
  if (targetField.RelatedField) {
    const relatedKey = listRecord[targetField.RelatedField]
    if (relatedKey !== null && relatedKey !== undefined && relatedKey !== '') {
      return String(relatedKey)
    }
  }

  if (targetField.RelatedTable === 'UnitOfMeasure') {
    const code = listRecord.unit_of_measure ?? listRecord.code
    if (code !== null && code !== undefined && code !== '') return String(code)
  }

  if (targetField.RelatedTable === 'ItemUnitOfMeasure') {
    if (listRecord.id != null && listRecord.id !== '') return String(listRecord.id)
  }

  const direct = listRecord[targetField.Name]
  if (direct !== null && direct !== undefined && direct !== '') return String(direct)

  return String(listRecord.SystemId ?? '')
}
