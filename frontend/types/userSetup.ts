export interface UserSetup {
  id: number
  user: number
  userId: number
  username: string
  email: string
  fullName: string
  canSeeBuyingPrice: boolean
  canSeeProfitMargin: boolean
  canSeeItemCost: boolean
  canEditSalesPrice?: boolean
  canPostPreviousDates: boolean
  canReversePurchaseInvoice: boolean
  canReverseSalesInvoice: boolean
  canReverseItemJournal?: boolean
  canViewOnlyTheirSales: boolean
  notes: string
  createdAt: string
  updatedAt: string
}
