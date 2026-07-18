'use client'

import { useSession } from '@/context/SessionContext'
import { useBranchOptional } from '@/context/BranchContext'
import { Receipt } from '@/components/pos/Receipt'
import { resolveMediaUrl } from '@/lib/media'
import type { POSCompanyInfo, POSCompletedSale } from '@/types/pos'

interface POSReceiptDialogProps {
  open: boolean
  sale: POSCompletedSale | null
  company?: POSCompanyInfo | null
  onClose: () => void
}

function normalizeBranchCodeForReceipt(value: unknown): string | undefined {
  if (value == null) return undefined
  if (Array.isArray(value)) {
    const first = value[0]
    return typeof first === 'string' ? first : (first?.code ?? undefined)
  }
  const str = String(value).trim()
  if (!str) return undefined
  return str.split(/\r?\n/)[0].trim() || undefined
}

export function POSReceiptDialog({ open, sale, company, onClose }: POSReceiptDialogProps) {
  const { session } = useSession()
  const branch = useBranchOptional()

  if (!open || !sale) return null

  const branchCode = normalizeBranchCodeForReceipt(branch?.activeBranch?.code)
  const logoUrl = resolveMediaUrl(company?.logo ?? null)

  return (
    <Receipt
      isOpen={open}
      onClose={onClose}
      invoice={{
        invoice_no: sale.invoice_no ?? sale.receipt_no ?? 'N/A',
        customer_name: sale.customer_name ?? 'N/A',
        customer_no: sale.customer_no,
        total_amount: sale.total_amount,
        amount_received: sale.amount_received,
        change_amount: sale.change_amount,
        document_date: sale.document_date ?? new Date().toISOString().slice(0, 10),
        created_at: sale.created_at ?? new Date().toISOString(),
        total_excl_vat: sale.total_excl_vat,
        vat_amount: sale.vat_amount,
        vat_enabled: sale.vat_enabled,
        payment_method_details: sale.payment_method_details,
        lines: sale.lines.map((line) => ({
          item_name: line.item_name,
          quantity: line.quantity,
          unit_price: line.unit_price,
          total_amount: line.total_amount,
          total_price: line.total_amount,
          unit_of_measure: line.unit_of_measure,
        })),
      }}
      businessInfo={{
        name: company?.name ?? 'Company',
        displayName: company?.displayName ?? company?.name ?? 'Company',
        branchCode,
        logo: logoUrl ?? '',
        address: company?.address ?? '',
        phone: company?.phone ?? '',
        email: company?.email ?? '',
        website: company?.website,
        tin: company?.tin ?? '',
        vatNo: company?.vatNo ?? '',
      }}
      sellerInfo={{
        name: session?.user.fullName ?? session?.user.username ?? 'Unknown User',
        email: session?.user.email,
      }}
    />
  )
}
