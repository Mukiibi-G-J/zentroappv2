import type { PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

const NON_STOCK_ITEM_TYPES = new Set(['service', 'non-inventory'])

/** Inventory-only Item Card actions (no stock for Service / Non-Inventory). */
const INVENTORY_ONLY_ITEM_ACTIONS = new Set([
  'OpenItemOpeningBalance',
  'OpenItemAdjustments',
])

/** Actions that remain clickable on posted / read-only documents. */
const POSTED_DOCUMENT_ALLOWED_ACTIONS = new Set([
  'create_corrective_credit_memo',
  'reverse_transactions',
  'find_entries',
])

export function isPostedDocumentAllowedAction(action: PageAction): boolean {
  const name = (action.Name || '').trim().toLowerCase()
  if (POSTED_DOCUMENT_ALLOWED_ACTIONS.has(name)) return true
  return name.startsWith('reverse_') || name.startsWith('create_corrective_')
}

/** Whether a field or action should show for the current record (VisibleWhenField / VisibleWhenValues). */
export function isControlFieldVisible(
  field: Pick<PageControlField, 'VisibleWhenField' | 'VisibleWhenValues'>,
  record?: DataRecord | Record<string, unknown> | null,
): boolean {
  const whenField = field.VisibleWhenField?.trim()
  const allowed = field.VisibleWhenValues?.trim()
  if (!whenField || !allowed) return true

  const current = (record as Record<string, unknown> | undefined)?.[whenField]
  if (current === null || current === undefined) return false

  const currentStr = String(current).trim().toLowerCase()
  return allowed.split(',').some((v) => v.trim().toLowerCase() === currentStr)
}

/** Whether a ribbon action should show for the current record (VisibleWhenField / VisibleWhenValues). */
export function isPageActionVisible(action: PageAction, record?: DataRecord | null): boolean {
  if (!action.Visible) return false
  return isControlFieldVisible(action, record)
}

export function filterVisiblePageActions(
  actions: PageAction[],
  record?: DataRecord | null,
): PageAction[] {
  return actions.filter((a) => isPageActionVisible(a, record))
}

function itemTypeOf(record?: DataRecord | Record<string, unknown> | null): string {
  const raw = (record as Record<string, unknown> | undefined)?.type
  return String(raw ?? '').trim().toLowerCase()
}

/** Whether a visible ribbon action may be clicked for the current record. */
export function isPageActionEnabled(
  action: PageAction,
  record?: DataRecord | null,
): boolean {
  if (!INVENTORY_ONLY_ITEM_ACTIONS.has(action.Name)) return true
  const itemType = itemTypeOf(record)
  if (!itemType) return true
  return !NON_STOCK_ITEM_TYPES.has(itemType)
}

export function pageActionDisabledReason(
  action: PageAction,
  record?: DataRecord | null,
): string | null {
  if (isPageActionEnabled(action, record)) return null
  if (INVENTORY_ONLY_ITEM_ACTIONS.has(action.Name)) {
    return 'Not available for Service or Non-Inventory items'
  }
  return null
}
