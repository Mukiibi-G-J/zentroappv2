import type { Page, PageControl, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import { getRecordFieldValue } from '@/lib/recordFieldValue'

export const SET_APPLIES_TO_ID_ACTION = '#set-applies-to-id'
export const SHOW_SELECTED_ONLY_ACTION = '#show-selected-only'

/** Lines repeater / group bound to the page source table. */
export function findWorksheetLinesControl(page: Page | null | undefined): PageControl | undefined {
  if (!page) return undefined
  const source = (page.SourceTable || '').trim()
  return page.PageControls.find(
    (c) =>
      (c.ControlType === 'Group' || c.ControlType === 'Repeater')
      && !!c.SourceTable
      && (!source || c.SourceTable === source),
  )
}

/** Summary footer group (no source table). */
export function findWorksheetFooterControl(page: Page | null | undefined): PageControl | undefined {
  return page?.PageControls.find(
    (c) => c.ControlType === 'Group' && !c.SourceTable,
  )
}

export function findHeaderGroupControl(page: Page | null | undefined): PageControl | undefined {
  return page?.PageControls.find(
    (c) => c.ControlType === 'Group' || c.ControlType === 'Repeater',
  )
}

export function buildContextLineFilters(
  page: Page | null | undefined,
  contextValue: string | undefined,
): Record<string, string> | undefined {
  const field = (page?.ContextFilterField || '').trim()
  if (!field || !contextValue) return undefined
  return { [field]: contextValue }
}

export function visibleLineFields(
  fields: PageControlField[] | undefined,
  contextFilterField?: string | null,
): PageControlField[] {
  const visible = fields?.filter((f) => f.Visible) ?? []
  const ctxField = (contextFilterField || '').trim()
  return visible.filter((f) => {
    if (f.PrimaryKey && f.Name === 'id') return false
    if (ctxField && f.Name === ctxField) return false
    return true
  })
}

/** BC-style apply worksheets: Worksheet + header card + context filter, opened as dialog. */
export function isDialogApplyWorksheet(page: Page | null | undefined): boolean {
  if (!page || page.PageType !== 'Worksheet') return false
  if (!page.HeaderPageId || !page.ContextFilterField) return false
  return page.SourceTable === 'VendorLedger' || page.SourceTable === 'CustomerLedgerEntry'
}

/** Context-filtered worksheets with editable lines (e.g. Item Tracking Lines). */
export function isEditableContextWorksheet(page: Page | null | undefined): boolean {
  if (!page || page.PageType !== 'Worksheet') return false
  if (page.Name === 'PostedItemTrackingLines' || page.Name === 'ItemTrackingLinesWorksheet') {
    return true
  }
  if (!page.HeaderPageId || !page.ContextFilterField) return false
  return !isDialogApplyWorksheet(page)
}

export function worksheetShowsSearch(page: Page | null | undefined, variant: 'page' | 'modal'): boolean {
  if (variant === 'modal') return false
  if (isDialogApplyWorksheet(page)) return false
  return true
}

const LEDGER_VIRTUAL_FIELDS = new Set([
  'appln_remaining_amount',
  'amount_to_apply',
  'appln_amount_to_apply',
])

export function isWorksheetVirtualField(field: PageControlField): boolean {
  return LEDGER_VIRTUAL_FIELDS.has(field.Name)
}

export function rowRemainingAmount(row: DataRecord): number {
  const rem = getRecordFieldValue(row, 'remaining_amount')
  if (rem !== null && rem !== undefined && rem !== '') {
    const n = Number(rem)
    if (!Number.isNaN(n)) return n
  }
  const amt = Number(getRecordFieldValue(row, 'amount'))
  return Number.isNaN(amt) ? 0 : amt
}

export function appliesToIdDisplay(
  row: DataRecord,
  overrides: Record<string, string>,
): string {
  if (row.SystemId in overrides) {
    return overrides[row.SystemId]
  }
  const existing = getRecordFieldValue(row, 'applies_to_id')
  if (existing !== null && existing !== undefined && existing !== '') {
    return String(existing)
  }
  return ''
}

export function isRowMarkedForPayment(
  row: DataRecord,
  appliesToOverrides: Record<string, string>,
  paymentDocNo: string,
): boolean {
  if (!paymentDocNo) return false
  return appliesToIdDisplay(row, appliesToOverrides) === paymentDocNo
}

export function getAmountToApplyForRow(
  row: DataRecord,
  appliesToOverrides: Record<string, string>,
  paymentDocNo: string,
  amountOverrides: Record<string, string>,
): number {
  if (!isRowMarkedForPayment(row, appliesToOverrides, paymentDocNo)) return 0
  const stored = amountOverrides[row.SystemId]
  if (stored !== undefined && stored !== '') {
    const n = Number(String(stored).replace(/,/g, ''))
    if (!Number.isNaN(n)) return n
  }
  return rowRemainingAmount(row)
}

export function amountToApplyInputValue(
  row: DataRecord,
  appliesToOverrides: Record<string, string>,
  paymentDocNo: string,
  amountOverrides: Record<string, string>,
): string {
  if (!isRowMarkedForPayment(row, appliesToOverrides, paymentDocNo)) return ''
  if (row.SystemId in amountOverrides) return amountOverrides[row.SystemId]
  return formatDecimalDisplay(rowRemainingAmount(row))
}

export function parseAmountInput(raw: string): number | null {
  const trimmed = raw.trim().replace(/,/g, '')
  if (trimmed === '' || trimmed === '-') return null
  const n = Number(trimmed)
  return Number.isNaN(n) ? null : n
}

/** BC: Amount to Apply must have the same sign as Remaining Amount (zero is allowed). */
export function amountToApplySignIsValid(remaining: number, amountToApply: number): boolean {
  if (amountToApply === 0) return true
  if (remaining === 0) return amountToApply === 0
  return Math.sign(remaining) === Math.sign(amountToApply)
}

export function buildAmountToApplySignError(
  partyKind: 'vendor' | 'customer',
  entryNo: number | string,
): string {
  const table =
    partyKind === 'customer' ? 'Customer Ledger Entry' : 'Vendor Ledger Entry'
  return `Amount to Apply must have the same sign as Remaining Amount in ${table} Entry No.='${entryNo}'.`
}

export function getLedgerEntryId(record: DataRecord): number {
  const id = Number(getRecordFieldValue(record, 'id'))
  if (id) return id
  const entryNo = Number(getRecordFieldValue(record, 'entry_no'))
  return entryNo || 0
}

export function isSetAppliesToIdAction(action: { ActionRelativeUrl?: string | null; Name?: string }): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === SET_APPLIES_TO_ID_ACTION || action.Name === 'SetAppliesToId'
}

export function isShowSelectedOnlyAction(action: { ActionRelativeUrl?: string | null; Name?: string }): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === SHOW_SELECTED_ONLY_ACTION || action.Name === 'ShowSelectedOnly'
}
