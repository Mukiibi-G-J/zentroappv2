import type { PageControlField } from '@/types/page'
import { parseIsoDate, parseTypedDate, toIsoDate } from '@/lib/dateFormat'

export function isCodeField(field: PageControlField): boolean {
  return field.FieldType === 'Code'
}

/** Display value while editing a list inline Code field. */
export function normalizeListFieldInputValue(field: PageControlField, value: unknown): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return isCodeField(field) ? text.toUpperCase() : text
}

/** Normalize date values to YYYY-MM-DD for API storage. */
export function normalizeDateSaveValue(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date && !Number.isNaN(value.getTime())) return toIsoDate(value)
  const text = String(value).trim()
  if (!text) return null
  const parsed = parseIsoDate(text) ?? parseTypedDate(text)
  return parsed ? toIsoDate(parsed) : text
}

/** Normalize a list inline value before comparing or saving. */
export function normalizeListFieldSaveValue(field: PageControlField, value: unknown): unknown {
  if (value === '' || value === undefined) return null
  if (field.FieldType === 'Date') {
    return normalizeDateSaveValue(value)
  }
  if (field.FieldType === 'DateTime') {
    const normalized = normalizeDateSaveValue(value)
    if (!normalized) return null
    const raw = String(value).trim()
    const timePart = raw.includes('T') ? raw.slice(11, 19) : ''
    return timePart ? `${normalized}T${timePart}` : normalized
  }
  if (isCodeField(field) && typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed ? trimmed.toUpperCase() : null
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (field.FieldType === 'Integer') {
      if (!trimmed) return null
      const n = Number(trimmed)
      return Number.isNaN(n) ? trimmed : Math.trunc(n)
    }
    if (field.FieldType === 'Decimal') {
      if (!trimmed) return null
      const n = Number(trimmed)
      return Number.isNaN(n) ? trimmed : n
    }
    return trimmed
  }
  return value
}

export function listFieldValuesEqual(
  a: unknown,
  b: unknown,
  field: PageControlField,
): boolean {
  const left = normalizeListFieldSaveValue(field, a)
  const right = normalizeListFieldSaveValue(field, b)
  return left === right
}
