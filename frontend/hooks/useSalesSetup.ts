'use client'

import { useQuery } from '@tanstack/react-query'
import { salesService } from '@/services/sales.service'
import type { POSSalesSetup } from '@/types/pos'

export function useSalesSetup() {
  return useQuery({
    queryKey: ['sales', 'setup'],
    queryFn: () => salesService.getSalesSetup(),
    staleTime: 60_000,
  })
}

export function normalizeSalesSetup(raw: POSSalesSetup | undefined): POSSalesSetup {
  if (!raw) {
    return {
      enable_line_discounts: false,
      enable_invoice_discounts: false,
      line_discounts_enabled: false,
      allow_price_editing: true,
    }
  }
  const enableLine =
    raw.enable_line_discounts ?? raw.line_discounts_enabled ?? false
  return {
    ...raw,
    enable_line_discounts: enableLine,
    line_discounts_enabled: enableLine,
    enable_invoice_discounts: raw.enable_invoice_discounts ?? false,
    allow_price_editing:
      raw.allow_price_editing ??
      (raw.disable_price_editing != null ? !raw.disable_price_editing : true),
  }
}
