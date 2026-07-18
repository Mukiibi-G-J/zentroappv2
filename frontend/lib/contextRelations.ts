import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

export function hasContextRelation(field: PageControlField): boolean {
  return !!(field.HasTableRelation && field.RelationContextField)
}

export function contextRelationValue(
  field: PageControlField,
  record: DataRecord | Record<string, unknown>,
): string | null {
  if (!field.RelationContextField) return null
  const v = (record as Record<string, unknown>)[field.RelationContextField]
  if (v != null && String(v).trim()) return String(v)
  return field.RelationContextDefault?.trim() || null
}

export function contextRelationCacheKey(
  field: PageControlField,
  record: DataRecord | Record<string, unknown>,
): string | null {
  const val = contextRelationValue(field, record)
  if (!val) return null
  return `${field.PageControlFieldId}:${val}`
}

export function buildRelationRecordValues(
  field: PageControlField,
  record: DataRecord | Record<string, unknown>,
): Record<string, string> | undefined {
  if (!field.RelationContextField) return undefined
  const val = contextRelationValue(field, record)
  if (!val) return undefined
  return { [field.RelationContextField]: val }
}

export function getDependentRelationFields(
  fields: PageControlField[],
  changedFieldName: string,
): PageControlField[] {
  return fields.filter(
    (f) => f.HasTableRelation && f.RelationContextField === changedFieldName,
  )
}

export function defaultValuesFromContextRelations(
  fields: PageControlField[],
): Record<string, string> {
  const defaults: Record<string, string> = {}
  for (const f of fields) {
    if (hasContextRelation(f) && f.RelationContextDefault) {
      defaults[f.RelationContextField!] = f.RelationContextDefault
    }
  }
  return defaults
}

export function collectContextValuesFromRecords(
  field: PageControlField,
  records: DataRecord[],
): Set<string> {
  const values = new Set<string>()
  if (!field.RelationContextField) return values
  for (const record of records) {
    const val = contextRelationValue(field, record)
    if (val) values.add(val)
  }
  if (values.size === 0 && field.RelationContextDefault?.trim()) {
    values.add(field.RelationContextDefault.trim())
  }
  return values
}
