'use client'

import { useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import type { Page } from '@/types/page'
import { resolveListFilterToken } from '@/lib/listPageFilters'

export function useDrillDownFilters(page: Page | undefined) {
  const searchParams = useSearchParams()
  const contextValue = searchParams.get('ctx')
  const contextLabel = searchParams.get('ctxLabel')
  const returnUrl = searchParams.get('return')
  const filterLabel = searchParams.get('filterLabel')
  const picker = searchParams.get('picker')

  const ctx2 = searchParams.get('ctx2')
  const ctx2Field = searchParams.get('ctx2Field')
  const postingDate = searchParams.get('posting_date')
  const postingDateFrom = searchParams.get('posting_date_from')
  const postingDateTo = searchParams.get('posting_date_to')
  const ledgerUserId = searchParams.get('ledger_user_id')
  const paymentMethod = searchParams.get('payment_method')
  const appliedToEntryId = searchParams.get('applied_to_entry_id')
  const vendorLedgerEntryId = searchParams.get('vendor_ledger_entry_id')
  const customerLedgerEntryId = searchParams.get('customer_ledger_entry_id')

  const filters: Record<string, string> = useMemo(() => {
    const result: Record<string, string> = {}
    if (page?.ContextFilterField && contextValue) {
      result[page.ContextFilterField] = contextValue
    }
    if (ctx2Field && ctx2) {
      result[ctx2Field] = ctx2
    }
    if (postingDate) {
      result.posting_date = resolveListFilterToken(postingDate)
    }
    if (postingDateFrom) {
      result.posting_date_from = resolveListFilterToken(postingDateFrom)
    }
    if (postingDateTo) {
      result.posting_date_to = resolveListFilterToken(postingDateTo)
    }
    if (ledgerUserId) {
      result.ledger_user_id = ledgerUserId
    }
    if (paymentMethod) {
      result.payment_method = paymentMethod
    }
    if (appliedToEntryId) {
      result.applied_to_entry_id = appliedToEntryId
    }
    if (vendorLedgerEntryId) {
      result.vendor_ledger_entry_id = vendorLedgerEntryId
    }
    if (customerLedgerEntryId) {
      result.customer_ledger_entry_id = customerLedgerEntryId
    }
    return result
  }, [
    page?.ContextFilterField,
    contextValue,
    ctx2,
    ctx2Field,
    postingDate,
    postingDateFrom,
    postingDateTo,
    ledgerUserId,
    paymentMethod,
    appliedToEntryId,
    vendorLedgerEntryId,
    customerLedgerEntryId,
  ])

  const isDrillDown = Object.keys(filters).length > 0

  return {
    filters,
    isDrillDown,
    contextValue,
    contextLabel,
    filterLabel,
    picker,
    returnUrl,
  }
}
