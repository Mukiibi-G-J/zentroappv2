import type { DataRecord } from '@/types/pagedata'

const FIELD_ALIASES: Record<string, string[]> = {
  amount: ['debit_amount'],
}

export function getRecordFieldValue(
  record: DataRecord | null | undefined,
  fieldName: string,
): unknown {
  if (!record) return undefined
  if (fieldName in record) return record[fieldName]
  const aliases = FIELD_ALIASES[fieldName]
  if (aliases) {
    for (const alias of aliases) {
      if (alias in record) return record[alias]
    }
  }
  return undefined
}

export function recordFieldValuesEqual(
  fieldName: string,
  a: unknown,
  b: unknown,
): boolean {
  if (a === b) return true
  // Coerce numbers and numeric strings
  const na = Number(a)
  const nb = Number(b)
  if (!isNaN(na) && !isNaN(nb)) return na === nb
  return String(a ?? '') === String(b ?? '')
}
