import type { Page } from '@/types/page'

/** True when the page should use the Card layout (not the detail/list-style form). */
export function isCardPage(page?: Pick<Page, 'PageType' | 'Name'> | null): boolean {
  if (!page) return false
  if (page.PageType === 'Card') return true
  return Boolean(page.Name?.endsWith('Card'))
}
