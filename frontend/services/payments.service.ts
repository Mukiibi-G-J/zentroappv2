import api from '@/lib/api'
import type { JournalApplySource } from '@/lib/applyEntriesContext'

export interface PaymentJournalVendorApplyResult {
  payment_journal: {
    system_id: string
    application_status?: string
    applies_to_doc_name?: string
    applies_to_object_id?: number | null
  }
  vendor_ledger_id: number
  vendor_ledger_document_no: string
}

export interface PaymentJournalCustomerApplyResult {
  payment_journal: {
    system_id: string
    application_status?: string
    applies_to_doc_name?: string
    applies_to_object_id?: number | null
  }
  customer_ledger_id: number
  customer_ledger_document_no: string
}

function extractError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { error?: string; detail?: string } } }).response?.data
    if (data?.detail) return String(data.detail).trim()
    if (data?.error) return data.error
  }
  if (err instanceof Error) return err.message
  return 'Request failed'
}

function applyPayload(
  systemId: string,
  journalSource?: JournalApplySource,
): { system_id: string; journal_source?: JournalApplySource } {
  const payload: { system_id: string; journal_source?: JournalApplySource } = { system_id: systemId }
  if (journalSource && journalSource !== 'payment_journal') {
    payload.journal_source = journalSource
  }
  return payload
}

export async function applyVendorEntry(
  systemId: string,
  vendorLedgerId: number,
  journalSource?: JournalApplySource,
): Promise<PaymentJournalVendorApplyResult> {
  try {
    const { data } = await api.post<PaymentJournalVendorApplyResult>(
      '/api/payments/payment-journal/apply-vendor-entry/',
      { ...applyPayload(systemId, journalSource), vendor_ledger_id: vendorLedgerId },
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export async function unapplyVendorEntry(
  systemId: string,
  journalSource?: JournalApplySource,
): Promise<void> {
  try {
    await api.post('/api/payments/payment-journal/unapply-vendor-entry/', applyPayload(systemId, journalSource))
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export async function applyCustomerEntry(
  systemId: string,
  customerLedgerId: number,
  journalSource?: JournalApplySource,
): Promise<PaymentJournalCustomerApplyResult> {
  try {
    const { data } = await api.post<PaymentJournalCustomerApplyResult>(
      '/api/payments/payment-journal/apply-customer-entry/',
      { ...applyPayload(systemId, journalSource), customer_ledger_id: customerLedgerId },
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export async function unapplyCustomerEntry(
  systemId: string,
  journalSource?: JournalApplySource,
): Promise<void> {
  try {
    await api.post('/api/payments/payment-journal/unapply-customer-entry/', applyPayload(systemId, journalSource))
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export interface SetLedgerAppliesToIdResult {
  ledger_entry_id: number
  applies_to_id: string
  document_no: string
  cleared?: boolean
}

export async function setLedgerAppliesToId(
  systemId: string,
  ledgerEntryId: number,
  party: 'vendor' | 'customer',
  journalSource?: JournalApplySource,
): Promise<SetLedgerAppliesToIdResult> {
  try {
    const { data } = await api.post<SetLedgerAppliesToIdResult>(
      '/api/payments/payment-journal/set-ledger-applies-to-id/',
      {
        ...applyPayload(systemId, journalSource),
        ledger_entry_id: ledgerEntryId,
        party,
      },
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export async function clearLedgerAppliesToId(
  systemId: string,
  ledgerEntryId: number,
  party: 'vendor' | 'customer',
  journalSource?: JournalApplySource,
): Promise<SetLedgerAppliesToIdResult> {
  try {
    const { data } = await api.post<SetLedgerAppliesToIdResult>(
      '/api/payments/payment-journal/clear-ledger-applies-to-id/',
      {
        ...applyPayload(systemId, journalSource),
        ledger_entry_id: ledgerEntryId,
        party,
      },
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export async function clearAppliesToStamps(
  systemId: string,
  party: 'vendor' | 'customer',
  journalSource?: JournalApplySource,
): Promise<{ document_no: string; cleared_count: number }> {
  try {
    const { data } = await api.post<{ document_no: string; cleared_count: number }>(
      '/api/payments/payment-journal/clear-applies-to-stamps/',
      {
        ...applyPayload(systemId, journalSource),
        party,
      },
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export interface QuickCustomerPaymentDebug {
  status?: string
  application_status?: string | null
  applies_to_doc_type?: string | null
  applies_to_object_id?: number | null
  applies_to_doc_name?: string | null
  external_document_no?: string | null
  description?: string | null
  bal_account_type?: string | null
  bal_account_object_id?: number | null
  bal_account_no?: string | null
  journal_dimension_set_id?: number | null
  invoice_document_no?: string
  invoice_ledger_id?: number
  invoice_dimension_set_id?: number | null
  invoice_global_dimension_1_id?: number | null
  invoice_applies_to_id?: string
  user_global_dimension_1_id?: number | null
  user_dimension_set_id?: number | null
}

export interface QuickCustomerPaymentResult {
  document_no: string
  system_id: string
  amount: number
  customer_id: number
  customer_no: string
  customer_name: string
  applied_document_no: string
  applied_ledger_id: number
  remaining_balance: number
  payment_method_id: number
  payment_method_code: string
  posted?: boolean
  create_only?: boolean
  debug?: QuickCustomerPaymentDebug
}

export async function quickCustomerPayment(payload: {
  customer_id: number
  amount: number
  payment_method_id: number
  /** Temporary: create + apply only, do not post (for debugging). */
  create_only?: boolean
}): Promise<QuickCustomerPaymentResult> {
  try {
    const { data } = await api.post<QuickCustomerPaymentResult>(
      '/api/payments/payment-journal/quick-customer-payment/',
      payload,
    )
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

/** @deprecated Use PaymentJournalVendorApplyResult */
export type PaymentJournalApplyResult = PaymentJournalVendorApplyResult
