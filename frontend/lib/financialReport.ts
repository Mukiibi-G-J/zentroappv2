import { ensureZentroPrintHideRootBeforePrint } from '@/hooks/useZentroPrintHideRoot'

export interface FinancialReportColumn {
  key: string
  line_no: number
  header: string
  column_type?: string
}

export interface FinancialReportRow {
  line_no: number
  row_no: string
  description: string
  row_type?: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
  indentation?: number
  amounts: Record<string, number | null>
  visible?: boolean
}

export interface FinancialReportData {
  report_name: string
  description?: string
  period_type?: string
  period_label?: string
  start_date?: string
  end_date?: string
  currency_code?: string
  columns: FinancialReportColumn[]
  rows: FinancialReportRow[]
}

export const FINANCIAL_REPORT_RECALCULATE_ACTION = 'recalculate_financial_report'
export const FINANCIAL_REPORT_PRINT_ACTION = 'print_financial_report'

export function isFinancialReportDateAction(actionName: string): boolean {
  const normalized = actionName.trim().toLowerCase()
  return (
    normalized === FINANCIAL_REPORT_RECALCULATE_ACTION
    || normalized === FINANCIAL_REPORT_PRINT_ACTION
  )
}

export function defaultFinancialReportDateRange(): { startDate: string; endDate: string } {
  return dateRangeForPeriodType('Month')
}

export function isoDateFromRecordValue(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null
  const raw = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return null
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const day = String(parsed.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function reportDatesFromRecord(
  record: Record<string, unknown> | null | undefined,
): { startDate: string; endDate: string } {
  const start = isoDateFromRecordValue(record?.start_date)
  const end = isoDateFromRecordValue(record?.end_date)
  if (start && end) return { startDate: start, endDate: end }
  return dateRangeForPeriodType(String(record?.period_type || 'Month'))
}

export const FINANCIAL_REPORT_START_DATE_FIELD = {
  Name: 'start_date',
  Caption: 'Start Date',
  FieldType: 'Date',
} as const

export const FINANCIAL_REPORT_END_DATE_FIELD = {
  Name: 'end_date',
  Caption: 'End Date',
  FieldType: 'Date',
} as const

export function dateRangeForPeriodType(
  periodType: string,
  anchorIso?: string,
): { startDate: string; endDate: string } {
  const anchor = anchorIso ? parseIsoLocalDate(anchorIso) : new Date()
  let start: Date
  let end: Date

  switch (periodType) {
    case 'Day':
      start = new Date(anchor)
      end = new Date(anchor)
      break
    case 'Week': {
      const day = anchor.getDay()
      const mondayOffset = day === 0 ? -6 : 1 - day
      start = new Date(anchor)
      start.setDate(anchor.getDate() + mondayOffset)
      end = new Date(start)
      end.setDate(start.getDate() + 6)
      break
    }
    case 'Quarter': {
      const quarter = Math.floor(anchor.getMonth() / 3)
      start = new Date(anchor.getFullYear(), quarter * 3, 1)
      end = new Date(anchor.getFullYear(), quarter * 3 + 3, 0)
      break
    }
    case 'Year':
      start = new Date(anchor.getFullYear(), 0, 1)
      end = new Date(anchor.getFullYear(), 11, 31)
      break
    case 'Accounting Period':
      start = new Date(1900, 0, 1)
      end = new Date(anchor)
      break
    case 'Month':
    default:
      start = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
      end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)
      break
  }

  return { startDate: toIsoDate(start), endDate: toIsoDate(end) }
}

function parseIsoLocalDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, (month || 1) - 1, day || 1)
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export interface FinancialReportDownloadContent {
  FileName: string
  MimeType: string
  FileBase64: string
}

export function isFinancialReportDownloadContent(
  value: unknown,
): value is FinancialReportDownloadContent {
  return (
    typeof value === 'object'
    && value !== null
    && typeof (value as FinancialReportDownloadContent).FileName === 'string'
    && typeof (value as FinancialReportDownloadContent).MimeType === 'string'
    && typeof (value as FinancialReportDownloadContent).FileBase64 === 'string'
  )
}

export function downloadBase64File(base64: string, fileName: string, mimeType: string) {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  const blob = new Blob([bytes], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}

/** Open a base64 PDF in a new tab (browser preview) without forcing a download. */
export function openFinancialReportPdfPreview(base64: string, mimeType = 'application/pdf') {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  const blob = new Blob([bytes], { type: mimeType || 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const previewWindow = window.open(url, '_blank', 'noopener,noreferrer')
  if (!previewWindow) {
    URL.revokeObjectURL(url)
    throw new Error('Pop-up blocked — allow pop-ups to preview the PDF')
  }
  // Keep the blob URL alive while the tab loads; revoke later.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export function isFinancialReportData(value: unknown): value is FinancialReportData {
  return (
    typeof value === 'object'
    && value !== null
    && 'columns' in value
    && 'rows' in value
    && Array.isArray((value as FinancialReportData).columns)
    && Array.isArray((value as FinancialReportData).rows)
  )
}

export function isFinancialReportPrintContent(
  value: unknown,
): value is { Type: 'FinancialReportPrint'; Html: string; FinancialReport?: FinancialReportData } {
  return (
    typeof value === 'object'
    && value !== null
    && (value as { Type?: string }).Type === 'FinancialReportPrint'
    && typeof (value as { Html?: string }).Html === 'string'
  )
}

export function financialReportAmountFieldName(columnKey: string): string {
  return `report_amount_${columnKey}`
}

export function openFinancialReportPrintHtml(html: string) {
  const printWindow = window.open('', '_blank', 'width=900,height=720')
  if (!printWindow) {
    throw new Error('Pop-up blocked — allow pop-ups to print the report')
  }
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
  ensureZentroPrintHideRootBeforePrint()
  setTimeout(() => {
    try {
      printWindow.print()
      printWindow.close()
    } catch {
      /* window may already be closed */
    }
  }, 400)
}

export function buildAmountsByLineNo(data: FinancialReportData): Map<number, Record<string, number | null>> {
  const map = new Map<number, Record<string, number | null>>()
  for (const row of data.rows) {
    map.set(row.line_no, row.amounts)
  }
  return map
}

export function visibleFinancialReportLineNos(data: FinancialReportData): Set<number> | null {
  const hasHidden = data.rows.some((row) => row.visible === false)
  if (!hasHidden) return null
  return new Set(data.rows.filter((row) => row.visible !== false).map((row) => row.line_no))
}
