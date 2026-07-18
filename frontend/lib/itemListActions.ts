import type { PageAction } from '@/types/page'

export const ITEM_LIST_PAGE = 'ItemList'

export const ITEM_LIST_DOWNLOAD_TEMPLATE = '#download-item-template'
export const ITEM_LIST_IMPORT = '#import-items'
export const ITEM_LIST_EXPORT = '#export-items'

export function isItemListHashAction(action: PageAction): boolean {
  const target = (action.ActionRelativeUrl || '').trim()
  return (
    target === ITEM_LIST_DOWNLOAD_TEMPLATE
    || target === ITEM_LIST_IMPORT
    || target === ITEM_LIST_EXPORT
  )
}
