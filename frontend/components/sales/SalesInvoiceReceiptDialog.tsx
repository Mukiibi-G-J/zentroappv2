'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useSession } from '@/context/SessionContext'
import { Receipt } from '@/components/pos/Receipt'
import { resolveMediaUrl } from '@/lib/media'
import { salesService, type SalesInvoiceForReceipt } from '@/services/sales.service'
import type { POSCompanyInfo } from '@/types/pos'

interface SalesInvoiceReceiptDialogProps {
  systemId: string | null
  open: boolean
  onClose: () => void
}

function lineDisplayName(line: NonNullable<SalesInvoiceForReceipt['lines']>[number]): string {
  return (
    line.item_name?.trim() ||
    line.resource_name?.trim() ||
    line.description?.trim() ||
    'Item'
  )
}

export function SalesInvoiceReceiptDialog({ systemId, open, onClose }: SalesInvoiceReceiptDialogProps) {
  const { session } = useSession()
  const [invoice, setInvoice] = useState<SalesInvoiceForReceipt | null>(null)
  const [company, setCompany] = useState<POSCompanyInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !systemId) {
      setInvoice(null)
      setCompany(null)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      salesService.getInvoiceForReceipt(systemId),
      salesService.getCompanyInfo(),
    ])
      .then(([inv, co]) => {
        if (cancelled) return
        setInvoice(inv)
        setCompany(co)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load invoice for printing')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [open, systemId])

  if (!open) return null

  if (loading) {
    return (
      <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/40">
        <div className="flex items-center gap-3 rounded-xl bg-white px-6 py-4 shadow-xl text-sm text-mainTextColor">
          <Loader2 size={18} className="animate-spin text-primaryColor" />
          Preparing receipt…
        </div>
      </div>
    )
  }

  if (error || !invoice) {
    return (
      <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/40">
        <div className="rounded-xl bg-white p-6 shadow-xl max-w-sm w-full mx-4">
          <h3 className="text-base font-semibold text-mainTextColor">Print failed</h3>
          <p className="mt-1 text-sm text-bodyText">{error ?? 'Invoice not found'}</p>
          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-strokeColor px-4 py-2 text-sm font-medium text-bodyText hover:bg-softBg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }

  const vatAmount = Number(invoice.total_vat_amount ?? 0)
  const totalAmount = Number(invoice.total_amount ?? 0)
  const logoUrl = resolveMediaUrl(company?.logo ?? null)
  const sellerName =
    invoice.user_name?.trim() ||
    session?.user.fullName ||
    session?.user.username ||
    'Unknown User'

  return (
    <Receipt
      isOpen={open}
      onClose={onClose}
      invoice={{
        invoice_no: invoice.invoice_no ?? 'N/A',
        customer_name: invoice.customer_name ?? 'N/A',
        total_amount: totalAmount,
        amount_received: invoice.amount_received,
        change_amount: invoice.change_amount,
        document_date: invoice.document_date ?? new Date().toISOString().slice(0, 10),
        created_at: invoice.created_at ?? new Date().toISOString(),
        total_excl_vat: vatAmount > 0 ? totalAmount - vatAmount : undefined,
        vat_amount: vatAmount > 0 ? vatAmount : undefined,
        vat_enabled: vatAmount > 0,
        payment_method_details: invoice.payment_method_details
          ? {
              id: invoice.payment_method_details.id ?? 0,
              code: invoice.payment_method_details.code ?? '',
              description: invoice.payment_method_details.description ?? '',
              requires_amount_received: Boolean(
                invoice.payment_method_details.requires_amount_received,
              ),
            }
          : undefined,
        lines: (invoice.lines ?? []).map((line) => ({
          item_name: lineDisplayName(line),
          quantity: line.quantity ?? 0,
          unit_price: line.unit_price ?? 0,
          total_amount: line.total_amount ?? 0,
          total_price: line.total_amount ?? 0,
          unit_of_measure: line.unit_of_measure,
        })),
      }}
      businessInfo={{
        name: company?.name ?? 'Company',
        displayName: company?.displayName ?? company?.name ?? 'Company',
        branchCode: invoice.branch_code ?? undefined,
        logo: logoUrl ?? '',
        address: company?.address ?? '',
        phone: company?.phone ?? '',
        email: company?.email ?? '',
        website: company?.website,
        tin: company?.tin ?? '',
        vatNo: company?.vatNo ?? '',
      }}
      sellerInfo={{
        name: sellerName,
        email: session?.user.email,
      }}
    />
  )
}
