import type { RelationOption } from '@/hooks/useRelationOptions'
import type { PageControlField } from '@/types/page'

function findRelationOption(
  value: string,
  options: RelationOption[],
): RelationOption | undefined {
  return (
    options.find((o) => o.value === value)
    ?? options.find((o) => o.code === value || o.label === value)
    ?? options.find((o) => o.label.startsWith(`${value} —`))
  )
}

export function resolveRelationSelectValue(
  value: unknown,
  options: RelationOption[],
): string {
  if (value === null || value === undefined || value === '') return ''
  const str = String(value)
  return findRelationOption(str, options)?.value ?? str
}

export function formatRelationDisplay(
  value: unknown,
  field: PageControlField,
  options: RelationOption[],
): string {
  if (value === null || value === undefined || value === '') return '—'

  const str = String(value)
  const match = findRelationOption(str, options)
  if (!match) return str

  // Application objects: Object ID column shows the numeric id; name is in the next column.
  if (field.RelatedTable === 'Objects') {
    if (field.Name === 'object_id' || field.RelatedDisplayField === 'object_id') {
      return match.label
    }
    return match.caption ?? match.name ?? match.label
  }

  if (field.RelatedTable === 'ItemUnitOfMeasure') {
    return match.code?.trim() || match.label
  }

  // Business-key relations (item no., location code, etc.): show only the key
  if (field.RelatedField === 'code' || field.RelatedField === 'no') {
    return match.label
  }

  // If the display field is a full_name-style field, show only the caption
  if (field.RelatedDisplayField === 'full_name' || field.RelatedDisplayField === 'name') {
    return match.caption ?? match.label
  }

  // Otherwise show "value — caption"
  if (match.caption) return `${match.label} — ${match.caption}`
  return match.label
}
