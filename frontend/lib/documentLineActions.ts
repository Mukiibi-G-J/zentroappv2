import type { PageAction } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { isLineNavigateAction } from '@/lib/cardAction'
import { filterVisiblePageActions } from '@/lib/pageActionVisibility'
import type { ApplyPaymentContext, ApplyEntriesPartyKind, JournalApplySource } from '@/lib/applyEntriesContext'

/** Seeded worksheet page names (BC Pages 232/233). */
export const APPLY_VENDOR_ENTRIES_PAGE_NAME = 'ApplyVendorEntries'
export const APPLY_CUSTOMER_ENTRIES_PAGE_NAME = 'ApplyCustomerEntries'

/** Page-action URL tokens for opening Apply Entries worksheets (BC Pages 232/233). */
export const APPLY_VENDOR_ENTRIES_ACTION = '#apply-entries'
export const APPLY_CUSTOMER_ENTRIES_ACTION = '#apply-customer-entries'

export type { ApplyEntriesPartyKind }
export type ApplyEntriesContext = ApplyPaymentContext

export const ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME = 'ItemTrackingLinesWorksheet'
export const POSTED_ITEM_TRACKING_LINES_PAGE_NAME = 'PostedItemTrackingLines'

/** Page-action URL token for Item Tracking Lines (BC Page 6510). */
export const ITEM_TRACKING_LINES_ACTION = '#item-tracking-lines'

/** Page-action URL token for Posted Item Tracking Lines (BC Page 6511). */
export const POSTED_ITEM_TRACKING_LINES_ACTION = '#posted-item-tracking-lines'

/** Page-action URL token for deleting a tracking worksheet line. */
export const DELETE_TRACKING_LINE_ACTION = '#delete-line'

export function isDeleteTrackingLineAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === DELETE_TRACKING_LINE_ACTION || action.Name === 'DeleteLine'
}

export function isItemTrackingLinesAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === ITEM_TRACKING_LINES_ACTION || action.Name === 'ItemTrackingLines'
}

export function isPostedItemTrackingLinesAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === POSTED_ITEM_TRACKING_LINES_ACTION || action.Name === 'PostedItemTrackingLines'
}

export function isAnyItemTrackingLinesAction(action: PageAction): boolean {
  return isItemTrackingLinesAction(action) || isPostedItemTrackingLinesAction(action)
}

export function isApplyVendorEntriesAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === APPLY_VENDOR_ENTRIES_ACTION || action.Name === 'ApplyVendorEntries'
}

export function isApplyCustomerEntriesAction(action: PageAction): boolean {
  const url = (action.ActionRelativeUrl || '').trim()
  return url === APPLY_CUSTOMER_ENTRIES_ACTION || action.Name === 'ApplyCustomerEntries'
}

export function isApplyEntriesAction(action: PageAction): boolean {
  return isApplyVendorEntriesAction(action) || isApplyCustomerEntriesAction(action)
}

export function applyEntriesPartyKind(action: PageAction): ApplyEntriesPartyKind | null {
  if (isApplyVendorEntriesAction(action)) return 'vendor'
  if (isApplyCustomerEntriesAction(action)) return 'customer'
  return null
}

function normalizeAccountType(line: DataRecord): string {
  return String(line.account_type ?? '').trim().toLowerCase()
}

export function isVendorPaymentLine(line: DataRecord | null | undefined): boolean {
  if (!line) return false
  const accountNo = String(line.account_no ?? '').trim()
  return normalizeAccountType(line) === 'vendor' && accountNo.length > 0
}

export function isCustomerPaymentLine(line: DataRecord | null | undefined): boolean {
  if (!line) return false
  const accountNo = String(line.account_no ?? '').trim()
  return normalizeAccountType(line) === 'customer' && accountNo.length > 0
}

function lineScopedPageActions(actions: PageAction[] | undefined): PageAction[] {
  if (!actions?.length) return []
  return actions.filter(
    (action) =>
      action.Visible
      && (action.RibbonTab === 'Line' || action.RibbonTab === 'Home' || !action.RibbonTab?.trim()),
  )
}

/** Line-scoped navigation actions (e.g. open Permission Set card from User Permission Sets). */
export function visibleNavigateLinePageActions(
  actions: PageAction[] | undefined,
  line: DataRecord | null,
): PageAction[] {
  if (!line) return []
  return filterVisiblePageActions(
    lineScopedPageActions(actions).filter((action) => isLineNavigateAction(action)),
    line,
  )
}

/** Line-scoped page actions (Functions / row menu), e.g. Apply Entries by account type. */
export function visibleLinePageActions(
  actions: PageAction[] | undefined,
  line: DataRecord | null,
): PageAction[] {
  if (!line) return []
  return filterVisiblePageActions(
    lineScopedPageActions(actions).filter((action) => isApplyEntriesAction(action)),
    line,
  )
}

/** Line-scoped item tracking actions (open or posted purchase lines). */
export function visibleItemTrackingLinePageActions(
  actions: PageAction[] | undefined,
  line: DataRecord | null,
  opts?: { posted?: boolean },
): PageAction[] {
  if (!line) return []
  const predicate = opts?.posted ? isPostedItemTrackingLinesAction : isItemTrackingLinesAction
  return filterVisiblePageActions(
    lineScopedPageActions(actions).filter((action) => predicate(action)),
    line,
  )
}

export function buildApplyEntriesContext(
  line: DataRecord,
  paymentHeader: DataRecord,
  journalSource: JournalApplySource = 'payment_journal',
): ApplyPaymentContext | null {
  if (isVendorPaymentLine(line)) {
    const vendorNo = String(line.account_no ?? '').trim()
    return {
      partyKind: 'vendor',
      paymentSystemId: String(paymentHeader.SystemId),
      paymentHeader,
      partyNo: vendorNo,
      partyName: String(line.account_name ?? paymentHeader.account_name ?? '').trim() || undefined,
      appliedLedgerId:
        typeof paymentHeader.applies_to_object_id === 'number'
          ? paymentHeader.applies_to_object_id
          : Number(paymentHeader.applies_to_object_id) || null,
      journalSource,
    }
  }

  if (isCustomerPaymentLine(line)) {
    const customerNo = String(line.account_no ?? '').trim()
    return {
      partyKind: 'customer',
      paymentSystemId: String(paymentHeader.SystemId),
      paymentHeader,
      partyNo: customerNo,
      partyName: String(line.account_name ?? paymentHeader.account_name ?? '').trim() || undefined,
      appliedLedgerId:
        typeof paymentHeader.applies_to_object_id === 'number'
          ? paymentHeader.applies_to_object_id
          : Number(paymentHeader.applies_to_object_id) || null,
      journalSource,
    }
  }

  return null
}

/** General journal: the line itself is the applying document (BC page 39). */
export function buildGeneralJournalApplyContext(line: DataRecord): ApplyPaymentContext | null {
  return buildApplyEntriesContext(line, line, 'general_journal_line')
}

/** Item no. from a purchase invoice line (unified ``no`` or legacy ``item`` FK). */
export function purchaseLineItemNo(line: DataRecord | null | undefined): string {
  if (!line) return ''
  const lineType = String(line.type ?? 'item').trim().toLowerCase()
  if (lineType !== 'item') return ''
  return String(line.no ?? line.item ?? '').trim()
}

/** @deprecated Use buildApplyEntriesContext */
export function buildApplyVendorEntriesContext(
  line: DataRecord,
  paymentHeader: DataRecord,
): ApplyPaymentContext | null {
  return buildApplyEntriesContext(line, paymentHeader)
}
