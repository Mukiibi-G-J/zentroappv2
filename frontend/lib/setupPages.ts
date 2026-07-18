import type { Page } from '@/types/page'

/** BC-style singleton setup cards — one row per tenant; open via setup-solo API. */
export const SETUP_CARD_PAGE_NAMES = new Set([
  'InventorySetupCard',
  'ManufacturingSetupCard',
  'GeneralLedgerSetupCard',
  'CompanyCard',
  'CompanySubscriptionCard',
])

export function isSetupSingletonCardPage(page: Pick<Page, 'Name'> | undefined): boolean {
  return Boolean(page?.Name && SETUP_CARD_PAGE_NAMES.has(page.Name))
}
