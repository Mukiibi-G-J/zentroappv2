/** Business Central–style receipt report ids (must match backend ReceiptReportId). */
export const ReceiptReportId = {
  SALES_RECEIPT: 50000,
  KITCHEN_ORDER: 50001,
  BAR_ORDER: 50002,
  GUEST_CHECK: 50003,
  PREPAYMENT_RECEIPT: 50004,
  PAYMENT_JOURNAL: 50005,
} as const

export type ReceiptReportIdValue = (typeof ReceiptReportId)[keyof typeof ReceiptReportId]
