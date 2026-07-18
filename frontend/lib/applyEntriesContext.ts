import type { DataRecord } from '@/types/pagedata'

export type ApplyEntriesPartyKind = 'vendor' | 'customer'

export type JournalApplySource = 'payment_journal' | 'general_journal_line'

export interface ApplyPaymentContext {
  partyKind: ApplyEntriesPartyKind
  paymentSystemId: string
  paymentHeader: DataRecord
  partyNo: string
  partyName?: string
  appliedLedgerId?: number | null
  journalSource?: JournalApplySource
  onApplied?: () => void
}
