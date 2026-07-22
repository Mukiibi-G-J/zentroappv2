/** Strip grouping commas before parsing or saving numeric input. */
export function parseNumericInput(value: string): string {
  return value.replace(/,/g, '').trim()
}

/**
 * Live-format a decimal amount while typing: commas in the integer part,
 * optional decimal (up to `fractionDigits`), empty string when cleared.
 * Does not force trailing zeros so the user can delete freely.
 */
export function formatAmountInput(value: string, fractionDigits = 2): string {
  const cleaned = parseNumericInput(value).replace(/[^\d.]/g, '')
  if (cleaned === '') return ''

  const hasDecimal = cleaned.includes('.')
  const [intRaw = '', ...decParts] = cleaned.split('.')
  const decRaw = decParts.join('').slice(0, fractionDigits)

  const intFormatted =
    intRaw === ''
      ? '0'
      : Number(intRaw).toLocaleString(undefined, { maximumFractionDigits: 0 })

  if (!hasDecimal) return intFormatted
  return `${intFormatted}.${decRaw}`
}

/** Cursor index in a comma-formatted amount after `digitCount` significant chars. */
export function amountInputCaretIndex(formatted: string, digitCount: number): number {
  if (digitCount <= 0) return 0
  let seen = 0
  for (let i = 0; i < formatted.length; i += 1) {
    if (formatted[i] !== ',') seen += 1
    if (seen >= digitCount) return i + 1
  }
  return formatted.length
}

export function formatDecimalDisplay(value: unknown, fractionDigits = 2): string {
  if (value === null || value === undefined || value === '') return ''
  const n = Number(parseNumericInput(String(value)))
  if (Number.isNaN(n)) return String(value)
  return n.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

/** Comma-grouped amount without forcing trailing `.00` (keeps real decimals). */
export function formatAmountDisplay(value: unknown, maxFractionDigits = 2): string {
  if (value === null || value === undefined || value === '') return ''
  const n = Number(parseNumericInput(String(value)))
  if (Number.isNaN(n)) return String(value)
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxFractionDigits,
  })
}

export function formatIntegerDisplay(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  const n = Number(parseNumericInput(String(value)))
  if (Number.isNaN(n)) return String(value)
  return n.toLocaleString()
}

export function formatNumericFieldDisplay(
  value: unknown,
  fieldType: 'Decimal' | 'Integer',
): string {
  if (value === null || value === undefined || value === '') return '—'
  if (fieldType === 'Decimal') return formatDecimalDisplay(value)
  return formatIntegerDisplay(value)
}
