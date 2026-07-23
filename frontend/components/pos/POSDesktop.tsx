'use client'

import type { PageAction } from '@/types/page'
import type { ReturnTypeUseSalesPOS } from '@/components/pos/posTypes'
import { POSActionBar } from './POSActionBar'
import { POSTodaySalesBar } from './POSTodaySalesBar'
import { POSCartPanel } from './POSCartPanel'
import { POSCheckoutDialog } from './POSCheckoutDialog'
import { POSDraftDialog } from './POSDraftDialog'
import { POSProductGrid } from './POSProductGrid'
import { POSReceiptDialog } from './POSReceiptDialog'
import { POSRecordPaymentDialog } from './POSRecordPaymentDialog'
import { POSTrackingDialog } from './POSTrackingDialog'

type POSState = ReturnTypeUseSalesPOS

interface POSDesktopProps {
  pos: POSState
  pageActions: PageAction[]
}

export function POSDesktop({ pos, pageActions }: POSDesktopProps) {
  return (
    <>
      <POSTodaySalesBar pos={pos} />

      {/* Cart column shares full height with actions + products (no dead space above cart). */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row lg:gap-4">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 lg:w-[58%]">
          <POSActionBar pageActions={pageActions} pos={pos} />

          <header className="shrink-0">
            <input
              type="search"
              placeholder="Search items by name or number…"
              value={pos.search}
              onChange={(e) => pos.setSearch(e.target.value)}
              className="w-full rounded-xl border border-strokeColor bg-white px-4 py-2.5 text-sm shadow-sm"
            />
          </header>
          {pos.error && (
            <div className="shrink-0 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
              {pos.error}
            </div>
          )}
          <POSProductGrid
            products={pos.products}
            favorites={pos.favorites}
            loading={pos.productsLoading}
            onSelect={pos.addProduct}
            onLoadMore={() => pos.fetchNextProducts()}
            hasMore={pos.hasMoreProducts}
          />
        </div>

        <div className="flex min-h-0 w-full flex-col lg:w-[42%] lg:min-w-88 lg:max-w-xl">
          <POSCartPanel
            cart={pos.cart}
            subtotal={pos.subtotal}
            total={pos.total}
            canEditPrice={pos.canEditPrice}
            enableLineDiscounts={pos.enableLineDiscounts}
            enableInvoiceDiscounts={pos.enableInvoiceDiscounts}
            invoiceDiscountType={pos.invoiceDiscountType}
            invoiceDiscountAmount={pos.invoiceDiscountAmount}
            invoiceDiscountPercentage={pos.invoiceDiscountPercentage}
            invoiceDiscountValue={pos.invoiceDiscountValue}
            onUpdateQuantity={pos.updateLineQuantity}
            onUpdatePrice={pos.updateLinePrice}
            onUpdateLineDiscount={pos.updateLineDiscount}
            onInvoiceDiscountTypeChange={pos.setInvoiceDiscountType}
            onInvoiceDiscountAmountChange={pos.setInvoiceDiscountAmount}
            onInvoiceDiscountPercentageChange={pos.setInvoiceDiscountPercentage}
            onRemove={pos.removeLine}
            onClear={pos.clearCart}
            onCheckout={pos.openCheckout}
            onSelectTracking={pos.openTrackingModal}
            lineRequiresTracking={pos.lineRequiresTracking}
          />
        </div>
      </div>

      <POSCheckoutDialog
        open={pos.checkoutOpen}
        subtotal={pos.total}
        amountReceived={pos.amountReceived}
        onAmountReceivedChange={pos.setAmountReceived}
        customers={pos.customers}
        selectedCustomer={pos.selectedCustomer}
        onCustomerChange={pos.setSelectedCustomer}
        onCustomersRefresh={pos.refreshCustomers}
        paymentMethods={pos.paymentMethods}
        selectedPaymentMethod={pos.selectedPaymentMethod}
        onPaymentMethodChange={pos.setSelectedPaymentMethod}
        isGeneralCustomer={pos.isGeneralCustomer}
        saleDate={pos.saleDate}
        onSaleDateChange={pos.setSaleDate}
        canPostPreviousDates={pos.canPostPreviousDates}
        loading={pos.loadingCheckout}
        onClose={() => pos.setCheckoutOpen(false)}
        onConfirm={pos.completeSale}
      />

      <POSRecordPaymentDialog
        open={pos.recordPaymentOpen}
        customers={pos.customers}
        paymentMethods={pos.paymentMethods}
        onCustomersRefresh={pos.refreshCustomers}
        onClose={() => pos.setRecordPaymentOpen(false)}
      />

      <POSDraftDialog
        open={pos.draftsOpen}
        drafts={pos.drafts}
        loading={pos.loadingDrafts}
        onClose={() => pos.setDraftsOpen(false)}
        onResume={pos.resumeDraft}
        onDelete={pos.deleteDraft}
      />

      <POSReceiptDialog
        open={pos.receiptOpen}
        sale={pos.completedSale}
        company={pos.companyInfo}
        onClose={() => {
          pos.setReceiptOpen(false)
          pos.setError(null)
        }}
      />

      <POSTrackingDialog
        open={pos.trackingOpen}
        itemName={pos.trackingLine?.name ?? ''}
        options={pos.trackingOptions}
        loading={pos.loadingTracking}
        mode={pos.trackingLine?.trackingCode?.require_serial_no ? 'serial' : 'lot'}
        requiredCount={pos.trackingLine?.quantity ?? 1}
        selectedLotNo={pos.trackingLine?.selectedLotNo}
        selectedSerialNos={pos.trackingLine?.selectedSerialNos}
        onClose={pos.closeTrackingModal}
        onSelectLot={pos.selectTracking}
        onConfirmSerials={pos.confirmSerials}
      />
    </>
  )
}
