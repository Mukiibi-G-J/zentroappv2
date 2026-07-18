import type { Page, PageAction, PageControlField } from '@/types/page'

export function getRibbonActions(page: Pick<Page, 'PageActions'> | null | undefined): PageAction[] {
  return (page?.PageActions ?? []).filter(
    (action) =>
      (action.ActionType ?? 'Ribbon') === 'Ribbon'
      && action.Visible !== false
      && (action.RibbonTab || 'Home') !== 'Row',
  )
}

/** Row ⋮ menu actions (BC navigation / Entry group on list pages). */
export function getRowMenuActions(page: Pick<Page, 'PageActions'> | null | undefined): PageAction[] {
  return (page?.PageActions ?? []).filter((action) => {
    const target = (action.ActionRelativeUrl || '').trim()
    if (!action.Visible || !target || action.RibbonTab === 'Scope') return false
    if (target.startsWith('#')) return false
    const actionType = action.ActionType ?? 'Ribbon'
    if (actionType !== 'Ribbon') return true
    const tab = (action.RibbonTab || '').trim()
    return tab === 'Row' || tab === 'Entry'
  })
}

export function hasRibbonActions(page: Pick<Page, 'PageActions'> | null | undefined): boolean {
  return getRibbonActions(page).length > 0
}

/** BC-style Edit List toggle (view links vs inline grid edit). */
export function supportsEditListToggle(
  page: Pick<Page, 'Editable' | 'ModifyAllowed' | 'CardPageId'> | null | undefined,
  fields: Pick<PageControlField, 'PrimaryKey' | 'HasDrillDownPage'>[],
): boolean {
  if (!page || page.Editable !== true || page.ModifyAllowed === false) return false
  if (fields.some((f) => f.PrimaryKey && f.HasDrillDownPage)) return true
  if (page.CardPageId) return true
  return false
}

/** Whether the list grid is currently in inline edit mode. */
export function isInlineEditingActive(
  page: Pick<Page, 'Editable' | 'ModifyAllowed' | 'CardPageId'> | null | undefined,
  editListMode: boolean,
  fields: Pick<PageControlField, 'PrimaryKey' | 'HasDrillDownPage'>[],
): boolean {
  if (!page || page.ModifyAllowed === false) return false
  if (supportsEditListToggle(page, fields)) return editListMode
  if (page.Editable === true) return true
  return !page.CardPageId
}

/** @deprecated Use isInlineEditingActive — kept for callers that only need legacy detection. */
export function isInlineListPage(
  page: Pick<Page, 'CardPageId' | 'ModifyAllowed' | 'Editable'> | null | undefined,
): boolean {
  if (!page) return false
  if (page.ModifyAllowed === false) return false
  if (page.Editable === true) return true
  return !page.CardPageId
}

/** Field editable in BC Edit List grid (includes PK drill-down keys in edit mode). */
export function canEditFieldInGrid(
  field: PageControlField,
  inlineEditingActive: boolean,
  listControlEditable: boolean,
  page: Pick<Page, 'ModifyAllowed'> | null | undefined,
): boolean {
  if (!inlineEditingActive || !listControlEditable || page?.ModifyAllowed === false || field.NoSeriesCode) {
    return false
  }
  if (field.Editable) return true
  return Boolean(field.PrimaryKey && field.HasDrillDownPage)
}

/** Show drill-down link (view mode) instead of inline editor. */
export function showDrillDownInList(
  field: PageControlField,
  inlineEditingActive: boolean,
): boolean {
  return field.HasDrillDownPage === true && !inlineEditingActive
}
