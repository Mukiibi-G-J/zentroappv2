const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/

const MONTH_INDEX: Record<string, number> = {
  jan: 0,
  feb: 1,
  mar: 2,
  apr: 3,
  may: 4,
  jun: 5,
  jul: 6,
  aug: 7,
  sep: 8,
  oct: 9,
  nov: 10,
  dec: 11,
}

function calendarDate(year: number, month: number, day: number): Date | null {
  const date = new Date(year, month, day)
  if (
    Number.isNaN(date.getTime()) ||
    date.getFullYear() !== year ||
    date.getMonth() !== month ||
    date.getDate() !== day
  ) {
    return null
  }
  return date
}

/** Parse YYYY-MM-DD (or ISO datetime prefix) as local calendar date. */
export function parseIsoDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const match = ISO_DATE.exec(String(value))
  if (!match) return null
  return calendarDate(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
}

/** Parse common typed formats: DD-MMM-YYYY, DD/MM/YYYY, YYYY-MM-DD. */
export function parseTypedDate(raw: string): Date | null {
  const text = raw.trim()
  if (!text) return null

  const iso = parseIsoDate(text)
  if (iso) return iso

  const namedMonth = /^(\d{1,2})[-/. ]([a-zA-Z]{3,9})[-/. ](\d{4})$/.exec(text)
  if (namedMonth) {
    const day = Number(namedMonth[1])
    const month = MONTH_INDEX[namedMonth[2].slice(0, 3).toLowerCase()]
    const year = Number(namedMonth[3])
    if (month !== undefined) return calendarDate(year, month, day)
  }

  const numeric = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/.exec(text)
  if (numeric) {
    const day = Number(numeric[1])
    const month = Number(numeric[2]) - 1
    const year = Number(numeric[3])
    return calendarDate(year, month, day)
  }

  return null
}

/** Format Date as YYYY-MM-DD for API storage. */
export function toIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Display format used on BC-style cards, e.g. 04-Jul-2026. */
export function formatDisplayDate(value: string | null | undefined): string {
  const date = parseIsoDate(value)
  if (!date) return value ? String(value) : ''
  const day = String(date.getDate()).padStart(2, '0')
  const month = date.toLocaleString('en-GB', { month: 'short' })
  return `${day}-${month}-${date.getFullYear()}`
}

/** Human-readable local date/time for list columns, e.g. 7/21/2026, 4:34 AM. */
export function formatDisplayDateTime(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  const datePart = date.toLocaleDateString()
  const timePart = date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `${datePart}, ${timePart}`
}

export function isSameCalendarDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function addMonths(date: Date, delta: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1)
}

export interface CalendarDay {
  date: Date
  inMonth: boolean
}

export function getCalendarDays(viewMonth: Date): CalendarDay[] {
  const year = viewMonth.getFullYear()
  const month = viewMonth.getMonth()
  const firstWeekday = new Date(year, month, 1).getDay()
  const days: CalendarDay[] = []

  for (let i = 0; i < 42; i += 1) {
    const date = new Date(year, month, 1 - firstWeekday + i)
    days.push({ date, inMonth: date.getMonth() === month })
  }

  return days
}
