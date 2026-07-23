'use client'



import { useCallback, useEffect, useMemo, useState } from 'react'

import { formatDecimalDisplay } from '@/lib/formatNumber'
import {
  computeInvoiceDiscountValue,
  invoiceDiscountsEnabled,
  lineDiscountsEnabled,
} from '@/lib/salesDiscountFields'

import { usePageDataInfinite } from '@/hooks/usePageData'

import { usePages } from '@/hooks/usePage'

import {

  fetchAllItemLedgerEntries,

  getItemByNo,

  itemRequiresTracking,

  pickAvailableLots,

  pickAvailableSerials,

} from '@/services/items.service'

import { salesService } from '@/services/sales.service'

import { fetchMyUserSetup } from '@/services/userSetup.service'

import { useSession } from '@/context/SessionContext'

import type {

  ItemTrackingCode,

  POSCartLine,

  POSCompanyInfo,

  POSCompletedSale,

  POSCustomer,

  POSDraftSale,

  POSPaymentMethod,

  POSProduct,

  POSSalesSetup,

  POSTrackingOption,

} from '@/types/pos'

import type { DataRecord } from '@/types/pagedata'



const MAX_DRAFTS = 5



function todayIsoDate(): string {

  const d = new Date()

  const y = d.getFullYear()

  const m = String(d.getMonth() + 1).padStart(2, '0')

  const day = String(d.getDate()).padStart(2, '0')

  return `${y}-${m}-${day}`

}



function newClientId(): string {

  return `line-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

}



function isGeneralCustomer(customer: POSCustomer | null): boolean {

  if (!customer) return false

  if (customer.customer_type === 'General') return true

  const name = customer.name.toLowerCase()

  return (

    name.includes('general') ||

    name.includes('walk-in') ||

    name.includes('cash customer')

  )

}



function lineRequiresTracking(line: POSCartLine): boolean {

  return itemRequiresTracking(line.trackingCode)

}



function lineTrackingComplete(line: POSCartLine): boolean {
  if (!lineRequiresTracking(line)) return true
  if (line.trackingCode?.require_serial_no) {
    const serials = line.selectedSerialNos ?? []
    return serials.length === line.quantity && serials.every((s) => s.trim())
  }
  return Boolean(line.selectedLotNo?.trim())
}

function validateTrackingLines(cart: POSCartLine[]): string | null {

  const missing = cart.filter((line) => !lineTrackingComplete(line))

  if (!missing.length) return null

  const names = missing.map((l) => l.name).join(', ')

  const serialMissing = missing.some((l) => l.trackingCode?.require_serial_no)

  return serialMissing
    ? `Select serial number(s) for: ${names}`
    : `Select a lot for: ${names}`

}



function recordToProduct(row: DataRecord): POSProduct | null {

  if (row.blocked === true) return null

  const no = String(row.no ?? '')

  const name = String(row.item_name ?? '')

  if (!no || !name) return null

  return {

    SystemId: String(row.SystemId ?? ''),

    no,

    item_name: name,

    type: row.type != null ? String(row.type) : undefined,

    unit_price: Number(row.unit_price ?? 0),

    inventory: row.inventory != null ? Number(row.inventory) : undefined,

    blocked: row.blocked === true,

  }

}



function normalizeSetup(raw: POSSalesSetup): POSSalesSetup {

  const enableLine = raw.enable_line_discounts ?? raw.line_discounts_enabled ?? false

  return {

    ...raw,

    enable_line_discounts: enableLine,

    line_discounts_enabled: enableLine,

    enable_invoice_discounts: raw.enable_invoice_discounts ?? false,

    allow_price_editing:

      raw.allow_price_editing ?? (raw.disable_price_editing != null ? !raw.disable_price_editing : true),

    prevent_price_below_original: raw.prevent_price_below_original ?? false,

  }

}



function buildSalePayload(

  cart: POSCartLine[],

  customer: POSCustomer,

  paymentMethod: POSPaymentMethod | null,

  status: 'Open' | 'Draft',

  salesSetup: POSSalesSetup,

  amountReceived: number,

  total: number,

  saleDate: string,

  invoiceDiscountType: 'amount' | 'percentage',

  invoiceDiscountAmount: number,

  invoiceDiscountPercentage: number,

) {

  const requiresTender = paymentMethod?.requires_amount_received !== false

  const invoiceOk = invoiceDiscountsEnabled(salesSetup)

  const lineOk = lineDiscountsEnabled(salesSetup)

  const hasInvoiceDiscount =

    invoiceOk &&

    ((invoiceDiscountType === 'amount' && invoiceDiscountAmount > 0) ||

      (invoiceDiscountType === 'percentage' && invoiceDiscountPercentage > 0))

  return {

    customer: customer.id,

    customer_name: customer.name,

    document_date: saleDate,

    posting_date: saleDate,

    status,

    amount_received: status === 'Open' && requiresTender ? amountReceived : 0,

    change_amount:

      status === 'Open' && requiresTender ? Math.max(0, amountReceived - total) : 0,

    payment_method: paymentMethod?.id,

    invoice_discount_type: hasInvoiceDiscount ? invoiceDiscountType : null,

    invoice_discount_amount: String(

      hasInvoiceDiscount && invoiceDiscountType === 'amount' ? invoiceDiscountAmount : 0,

    ),

    invoice_discount_percentage: String(

      hasInvoiceDiscount && invoiceDiscountType === 'percentage' ? invoiceDiscountPercentage : 0,

    ),

    lines: cart.map((line, index) => ({

      id: index + 1,

      item: line.no,

      item_no: line.no,

      item_name: line.name,

      quantity: String(line.quantity),

      unit_price: String(line.unitPrice),

      total_amount: String(line.quantity * line.unitPrice - (lineOk ? line.lineDiscountAmount : 0)),

      line_discount_amount: String(lineOk ? line.lineDiscountAmount : 0),

      unit_of_measure: line.unitOfMeasure,

      tracking_code: line.selectedLotNo ?? '',

      serial_nos: line.selectedSerialNos ?? [],

      description: '',

    })),

  }

}



export function useSalesPOS(itemListPageId?: number, itemListControlId?: number) {

  const { session } = useSession()

  const { data: pages = [] } = usePages()

  const resolvedItemPage = itemListPageId ?? pages.find((p) => p.Name === 'ItemList')?.PageId

  const resolvedControlId =

    itemListControlId ??

    pages

      .find((p) => p.PageId === resolvedItemPage)

      ?.PageControls?.find((c) => c.ControlType === 'Repeater')?.PageControlId



  const [search, setSearch] = useState('')

  const [cart, setCart] = useState<POSCartLine[]>([])

  const [customers, setCustomers] = useState<POSCustomer[]>([])

  const [selectedCustomer, setSelectedCustomer] = useState<POSCustomer | null>(null)

  const [paymentMethods, setPaymentMethods] = useState<POSPaymentMethod[]>([])

  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<POSPaymentMethod | null>(null)

  const [salesSetup, setSalesSetup] = useState<POSSalesSetup>({})

  const [invoiceDiscountType, setInvoiceDiscountType] = useState<'amount' | 'percentage'>('amount')

  const [invoiceDiscountAmount, setInvoiceDiscountAmount] = useState(0)

  const [invoiceDiscountPercentage, setInvoiceDiscountPercentage] = useState(0)

  const [companyInfo, setCompanyInfo] = useState<POSCompanyInfo | null>(null)

  const [amountReceived, setAmountReceived] = useState(0)

  const [saleDate, setSaleDate] = useState(todayIsoDate)

  const [canPostPreviousDates, setCanPostPreviousDates] = useState(true)

  const [canEditSalesPrice, setCanEditSalesPrice] = useState(false)

  const [checkoutOpen, setCheckoutOpen] = useState(false)

  const [recordPaymentOpen, setRecordPaymentOpen] = useState(false)

  const [receiptOpen, setReceiptOpen] = useState(false)

  const [draftsOpen, setDraftsOpen] = useState(false)

  const [drafts, setDrafts] = useState<POSDraftSale[]>([])

  const [loadingDrafts, setLoadingDrafts] = useState(false)

  const [completedSale, setCompletedSale] = useState<POSCompletedSale | null>(null)

  const [loadingCheckout, setLoadingCheckout] = useState(false)

  const [savingDraft, setSavingDraft] = useState(false)

  const [addingProduct, setAddingProduct] = useState(false)

  const [error, setError] = useState<string | null>(null)

  const [favorites, setFavorites] = useState<POSProduct[]>([])

  const [trackingOpen, setTrackingOpen] = useState(false)

  const [trackingClientId, setTrackingClientId] = useState<string | null>(null)

  const [trackingOptions, setTrackingOptions] = useState<POSTrackingOption[]>([])

  const [loadingTracking, setLoadingTracking] = useState(false)

  const [todayMySales, setTodayMySales] = useState(0)

  const [loadingTodayMySales, setLoadingTodayMySales] = useState(false)

  const [showTodayMySales, setShowTodayMySales] = useState(false)



  const productsQuery = usePageDataInfinite(

    resolvedItemPage ?? 0,

    resolvedControlId,

    search || undefined,

    { blocked: 'false' },

    { enabled: !!resolvedItemPage && !!resolvedControlId },

  )



  const products = useMemo(() => {

    const rows = productsQuery.data?.pages.flat() ?? []

    return rows.map(recordToProduct).filter((p): p is POSProduct => p != null)

  }, [productsQuery.data])



  const trackingLine = useMemo(

    () => cart.find((l) => l.clientId === trackingClientId) ?? null,

    [cart, trackingClientId],

  )



  const subtotal = useMemo(

    () =>

      cart.reduce((sum, line) => {

        const gross = line.quantity * line.unitPrice

        const disc = lineDiscountsEnabled(salesSetup) ? line.lineDiscountAmount || 0 : 0

        return sum + gross - disc

      }, 0),

    [cart, salesSetup],

  )



  const invoiceDiscountValue = useMemo(() => {

    if (!invoiceDiscountsEnabled(salesSetup)) return 0

    return computeInvoiceDiscountValue(

      subtotal,

      invoiceDiscountType,

      invoiceDiscountAmount,

      invoiceDiscountPercentage,

    )

  }, [

    salesSetup,

    subtotal,

    invoiceDiscountType,

    invoiceDiscountAmount,

    invoiceDiscountPercentage,

  ])



  const total = useMemo(

    () => Math.max(0, subtotal - invoiceDiscountValue),

    [subtotal, invoiceDiscountValue],

  )



  const applyCustomerPaymentMethod = useCallback(

    (customer: POSCustomer, methods: POSPaymentMethod[]) => {

      const cash =

        methods.find((m) => m.code.toUpperCase() === 'CASH') ??

        methods.find((m) => m.requires_amount_received) ??

        methods[0] ??

        null

      if (customer.payment_method && methods.length) {

        const customerMethod = methods.find((m) => m.id === customer.payment_method)

        if (customerMethod && !(isGeneralCustomer(customer) && customerMethod.code === 'NOT_PAID')) {

          setSelectedPaymentMethod(customerMethod)

          return

        }

      }

      setSelectedPaymentMethod(cash)

    },

    [],

  )



  const loadDefaults = useCallback(async () => {

    try {

      const [customerRows, methods, setup, favData, company, userSetup] = await Promise.all([

        salesService.getCustomers(),

        salesService.getPaymentMethods(),

        salesService.getSalesSetup(),

        salesService.getFavorites().catch(() => ({ slots: [], min_slots: 4 })),

        salesService.getCompanyInfo(),

        fetchMyUserSetup().catch(() => null),

      ])

      setCustomers(customerRows)

      setPaymentMethods(methods)

      setSalesSetup(normalizeSetup(setup))
      if (!lineDiscountsEnabled(normalizeSetup(setup))) {
        setCart((prev) =>
          prev.map((l) =>
            l.lineDiscountAmount ? { ...l, lineDiscountAmount: 0 } : l,
          ),
        )
      }
      if (!invoiceDiscountsEnabled(normalizeSetup(setup))) {
        setInvoiceDiscountAmount(0)
        setInvoiceDiscountPercentage(0)
      }

      setCompanyInfo(company)

      setCanPostPreviousDates(userSetup?.canPostPreviousDates ?? true)

      setCanEditSalesPrice(userSetup?.canEditSalesPrice ?? false)



      const general =

        customerRows.find(

          (c) =>

            c.name.toLowerCase().includes('general') ||

            c.no.toLowerCase().includes('general') ||

            c.name.toLowerCase().includes('walk-in'),

        ) ?? customerRows[0] ??

        null

      setSelectedCustomer(general)

      if (general) applyCustomerPaymentMethod(general, methods)



      setFavorites(

        favData.slots.map((s) => ({

          SystemId: s.item_system_id,

          no: s.item_no,

          item_name: s.item_name,

          unit_price: Number(s.unit_price ?? 0),

        })),

      )

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to load POS data')

    }

  }, [applyCustomerPaymentMethod])



  const refreshCustomers = useCallback(async () => {
    try {
      const customerRows = await salesService.getCustomers()
      setCustomers(customerRows)
    } catch {
      // Keep the existing list if refresh fails; selection still works via onCustomerChange.
    }
  }, [])



  const refreshTodayMySales = useCallback(async () => {

    const userId = session?.user.id

    if (!userId) {

      setTodayMySales(0)

      return

    }

    setLoadingTodayMySales(true)

    try {

      const today = todayIsoDate()

      const summary = await salesService.getSalesSummary({

        posting_date: today,

        user: String(userId),

      })

      setTodayMySales(Number(summary.total_sales ?? 0))

    } catch {

      setTodayMySales(0)

    } finally {

      setLoadingTodayMySales(false)

    }

  }, [session?.user.id])



  useEffect(() => {

    loadDefaults()

  }, [loadDefaults])



  useEffect(() => {

    void refreshTodayMySales()

  }, [refreshTodayMySales])



  useEffect(() => {

    if (selectedCustomer) applyCustomerPaymentMethod(selectedCustomer, paymentMethods)

  }, [selectedCustomer, paymentMethods, applyCustomerPaymentMethod])



  const addProduct = useCallback(async (product: POSProduct) => {

    if (addingProduct) return

    setAddingProduct(true)

    setError(null)

    try {

      const detail = await getItemByNo(product.no)

      const type = detail?.type ?? product.type

      const inventory = detail?.inventory ?? product.inventory

      if (type === 'Inventory' && inventory != null && inventory <= 0) {

        setError(`${product.item_name} is out of stock`)

        return

      }



      const trackingCode: ItemTrackingCode | null | undefined =

        detail?.tracking_code ?? product.tracking_code ?? null

      const unitOfMeasure = detail?.unit_of_measure ?? 'PCS'

      const unitPrice = detail?.unit_price ?? product.unit_price



      setCart((prev) => {

        const existing = prev.find((l) => l.no === product.no)

        if (existing) {

          if (type === 'Inventory' && inventory != null && existing.quantity + 1 > inventory) {

            setError(`Only ${inventory} units available for ${product.item_name}`)

            return prev

          }

          return prev.map((l) =>

            l.no === product.no ? { ...l, quantity: l.quantity + 1 } : l,

          )

        }

        return [

          ...prev,

          {

            clientId: newClientId(),

            systemId: detail?.system_id ?? product.SystemId,

            no: product.no,

            name: product.item_name,

            quantity: 1,

            unitPrice,

            originalPrice: unitPrice,

            unitOfMeasure,

            lineDiscountAmount: 0,

            trackingCode,

            selectedLotNo: undefined,

          },

        ]

      })

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to add item')

    } finally {

      setAddingProduct(false)

    }

  }, [addingProduct])



  const updateLineQuantity = useCallback((clientId: string, quantity: number) => {

    setCart((prev) =>

      prev

        .map((l) => (l.clientId === clientId ? { ...l, quantity: Math.max(0, quantity) } : l))

        .filter((l) => l.quantity > 0),

    )

  }, [])



  const updateLinePrice = useCallback((clientId: string, unitPrice: number) => {

    const target = cart.find((l) => l.clientId === clientId)

    if (!target) return

    let nextPrice = Math.max(0, unitPrice)

    const original = target.originalPrice ?? target.unitPrice

    if (salesSetup.prevent_price_below_original && nextPrice < original) {

      nextPrice = original

      setError(`Cannot set price below original (${formatDecimalDisplay(original)})`)

    } else {

      setError(null)

    }

    setCart((prev) =>

      prev.map((l) => (l.clientId === clientId ? { ...l, unitPrice: nextPrice } : l)),

    )

  }, [cart, salesSetup.prevent_price_below_original])



  const updateLineDiscount = useCallback((clientId: string, discount: number) => {

    if (!lineDiscountsEnabled(salesSetup)) return

    setCart((prev) =>

      prev.map((l) => {

        if (l.clientId !== clientId) return l

        const gross = l.quantity * l.unitPrice

        const clamped = Math.min(Math.max(0, discount), Math.max(0, gross))

        return { ...l, lineDiscountAmount: clamped }

      }),

    )

  }, [salesSetup])



  const removeLine = useCallback((clientId: string) => {

    setCart((prev) => prev.filter((l) => l.clientId !== clientId))

  }, [])



  const clearCart = useCallback(() => {

    setCart([])

    setAmountReceived(0)

    setInvoiceDiscountAmount(0)

    setInvoiceDiscountPercentage(0)

    setInvoiceDiscountType('amount')

    setError(null)

  }, [])



  const openTrackingModal = useCallback(async (clientId: string) => {

    const line = cart.find((l) => l.clientId === clientId)

    if (!line) return



    setTrackingClientId(clientId)

    setTrackingOpen(true)

    setTrackingOptions([])

    setLoadingTracking(true)

    setError(null)



    try {

      const entries = await fetchAllItemLedgerEntries(line.no)

      if (line.trackingCode?.require_serial_no) {
        setTrackingOptions(pickAvailableSerials(entries))
      } else {
        setTrackingOptions(pickAvailableLots(entries))
      }

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to load tracking options')

      setTrackingOptions([])

    } finally {

      setLoadingTracking(false)

    }

  }, [cart])



  const selectTracking = useCallback((lotNo: string) => {

    if (!trackingClientId) return

    setCart((prev) =>

      prev.map((l) =>

        l.clientId === trackingClientId
          ? { ...l, selectedLotNo: lotNo, selectedSerialNos: undefined }
          : l,

      ),

    )

    setTrackingOpen(false)

    setTrackingClientId(null)

    setTrackingOptions([])

  }, [trackingClientId])



  const confirmSerials = useCallback((serialNos: string[]) => {

    if (!trackingClientId) return

    setCart((prev) =>

      prev.map((l) =>

        l.clientId === trackingClientId
          ? {
              ...l,
              selectedSerialNos: serialNos,
              selectedLotNo: undefined,
              quantity: serialNos.length || l.quantity,
            }
          : l,

      ),

    )

    setTrackingOpen(false)

    setTrackingClientId(null)

    setTrackingOptions([])

  }, [trackingClientId])



  const closeTrackingModal = useCallback(() => {

    setTrackingOpen(false)

    setTrackingClientId(null)

    setTrackingOptions([])

  }, [])



  const openCheckout = useCallback(() => {

    if (!cart.length) {

      setError('Add at least one item to the cart')

      return

    }

    const trackingError = validateTrackingLines(cart)

    if (trackingError) {

      setError(trackingError)

      return

    }

    setError(null)

    setSaleDate(todayIsoDate())

    setAmountReceived(total)

    setCheckoutOpen(true)

  }, [cart, total])



  const openRecordPayment = useCallback(() => {
    setError(null)
    setRecordPaymentOpen(true)
  }, [])



  const loadDraftList = useCallback(async () => {

    setLoadingDrafts(true)

    try {

      const rows = await salesService.listDrafts(MAX_DRAFTS)

      setDrafts(rows)

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to load drafts')

    } finally {

      setLoadingDrafts(false)

    }

  }, [])



  const openDrafts = useCallback(async () => {

    setDraftsOpen(true)

    await loadDraftList()

  }, [loadDraftList])



  const resumeDraft = useCallback(

    async (draft: POSDraftSale) => {

      try {

        const full = await salesService.getSale(draft.id)

        const lines: POSCartLine[] = []

        for (const line of full.lines) {

          const detail = await getItemByNo(line.item_no)

          lines.push({

            clientId: newClientId(),

            systemId: detail?.system_id ?? '',

            no: line.item_no,

            name: line.item_name,

            quantity: line.quantity,

            unitPrice: line.unit_price,

            originalPrice: detail?.unit_price ?? line.unit_price,

            unitOfMeasure: detail?.unit_of_measure ?? 'PCS',

            lineDiscountAmount: line.line_discount_amount,

            trackingCode: detail?.tracking_code ?? null,

            selectedLotNo: undefined,

          })

        }

        setCart(lines)

        const customer = customers.find((c) => c.name === full.customer_name) ?? selectedCustomer

        if (customer) setSelectedCustomer(customer)

        await salesService.deleteSale(draft.id)

        setDraftsOpen(false)

        setError(null)

      } catch (e) {

        setError(e instanceof Error ? e.message : 'Failed to resume draft')

      }

    },

    [customers, selectedCustomer],

  )



  const deleteDraft = useCallback(

    async (draft: POSDraftSale) => {

      try {

        await salesService.deleteSale(draft.id)

        await loadDraftList()

      } catch (e) {

        setError(e instanceof Error ? e.message : 'Failed to delete draft')

      }

    },

    [loadDraftList],

  )



  const saveDraft = useCallback(async () => {

    if (!cart.length) {

      setError('Add at least one item before saving a draft')

      return

    }

    if (!selectedCustomer) {

      setError('Select a customer')

      return

    }

    const trackingError = validateTrackingLines(cart)

    if (trackingError) {

      setError(trackingError)

      return

    }

    setSavingDraft(true)

    setError(null)

    try {

      const existing = await salesService.listDrafts(MAX_DRAFTS)

      if (existing.length >= MAX_DRAFTS) {

        setError(`Maximum ${MAX_DRAFTS} POS drafts allowed. Resume or delete one first.`)

        return

      }

      await salesService.createSale(

        buildSalePayload(

          cart,

          selectedCustomer,

          selectedPaymentMethod,

          'Draft',

          salesSetup,

          amountReceived,

          total,

          saleDate,

          invoiceDiscountType,

          invoiceDiscountAmount,

          invoiceDiscountPercentage,

        ),

      )

      clearCart()

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to save draft')

    } finally {

      setSavingDraft(false)

    }

  }, [

    amountReceived,

    saleDate,

    cart,

    clearCart,

    salesSetup,

    selectedCustomer,

    selectedPaymentMethod,

    total,

    invoiceDiscountType,

    invoiceDiscountAmount,

    invoiceDiscountPercentage,

  ])



  const completeSale = useCallback(async () => {

    if (!selectedCustomer || !selectedPaymentMethod) {

      setError('Select customer and payment method')

      return

    }

    const trackingError = validateTrackingLines(cart)

    if (trackingError) {

      setError(trackingError)

      return

    }

    const requiresTender = selectedPaymentMethod.requires_amount_received !== false

    if (requiresTender && amountReceived < total) {

      setError('Amount received must cover the total')

      return

    }

    setLoadingCheckout(true)

    setError(null)

    let createdId: number | null = null

    try {

      const payload = buildSalePayload(

        cart,

        selectedCustomer,

        selectedPaymentMethod,

        'Open',

        salesSetup,

        amountReceived,

        total,

        saleDate,

        invoiceDiscountType,

        invoiceDiscountAmount,

        invoiceDiscountPercentage,

      )

      const created = await salesService.createSale(payload)

      createdId = created.id

      const postResult = await salesService.postInvoice(created.id)

      setCompletedSale({

        id: created.id,

        invoice_no: postResult.invoice_no ?? created.invoice_no,

        total_amount: total,

        amount_received: requiresTender ? amountReceived : 0,

        change_amount: requiresTender ? Math.max(0, amountReceived - total) : 0,

        customer_name: selectedCustomer.name,

        customer_no: selectedCustomer.no,

        payment_method_name: selectedPaymentMethod.description,

        payment_method_details: {

          id: selectedPaymentMethod.id,

          code: selectedPaymentMethod.code,

          description: selectedPaymentMethod.description,

          requires_amount_received: selectedPaymentMethod.requires_amount_received !== false,

        },

        document_date: saleDate,

        created_at: new Date().toISOString(),

        vat_enabled: salesSetup.vat_enabled,

        vat_amount: Number(postResult.invoice?.total_vat_amount ?? 0),

        total_excl_vat:

          salesSetup.vat_enabled && Number(postResult.invoice?.total_vat_amount ?? 0) > 0

            ? total - Number(postResult.invoice?.total_vat_amount ?? 0)

            : undefined,

        lines: cart.map((line) => ({

          item_name: line.name,

          quantity: line.quantity,

          unit_price: line.unitPrice,

          total_amount: line.quantity * line.unitPrice - line.lineDiscountAmount,

          unit_of_measure: line.unitOfMeasure,

        })),

      })

      setCheckoutOpen(false)

      setReceiptOpen(true)

      clearCart()

      void refreshTodayMySales()

    } catch (e) {

      if (createdId != null) {

        await salesService.deleteSale(createdId).catch(() => {})

      }

      setError(e instanceof Error ? e.message : 'Checkout failed')

    } finally {

      setLoadingCheckout(false)

    }

  }, [

    amountReceived,

    saleDate,

    cart,

    clearCart,

    salesSetup,

    selectedCustomer,

    selectedPaymentMethod,

    total,

    invoiceDiscountType,

    invoiceDiscountAmount,

    invoiceDiscountPercentage,

    refreshTodayMySales,

  ])



  return {

    search,

    setSearch,

    products,

    favorites,

    productsLoading: productsQuery.isLoading,

    productsFetching: productsQuery.isFetching || addingProduct,

    fetchNextProducts: productsQuery.fetchNextPage,

    hasMoreProducts: productsQuery.hasNextPage,

    cart,

    subtotal,

    total,

    enableLineDiscounts: lineDiscountsEnabled(salesSetup),

    enableInvoiceDiscounts: invoiceDiscountsEnabled(salesSetup),

    invoiceDiscountType,

    setInvoiceDiscountType,

    invoiceDiscountAmount,

    setInvoiceDiscountAmount,

    invoiceDiscountPercentage,

    setInvoiceDiscountPercentage,

    invoiceDiscountValue,

    customers,

    selectedCustomer,

    setSelectedCustomer,

    refreshCustomers,

    paymentMethods,

    selectedPaymentMethod,

    setSelectedPaymentMethod,

    amountReceived,

    setAmountReceived,

    saleDate,

    setSaleDate,

    canPostPreviousDates,

    canEditPrice:

      Boolean(canEditSalesPrice) && salesSetup.allow_price_editing !== false,

    checkoutOpen,

    setCheckoutOpen,

    recordPaymentOpen,

    setRecordPaymentOpen,

    openRecordPayment,

    receiptOpen,

    setReceiptOpen,

    draftsOpen,

    setDraftsOpen,

    drafts,

    loadingDrafts,

    completedSale,

    companyInfo,

    loadingCheckout,

    savingDraft,

    error,

    setError,

    addProduct,

    updateLineQuantity,

    updateLinePrice,

    updateLineDiscount,

    removeLine,

    clearCart,

    openCheckout,

    completeSale,

    saveDraft,

    openDrafts,

    resumeDraft,

    deleteDraft,

    isGeneralCustomer: isGeneralCustomer(selectedCustomer),

    trackingOpen,

    trackingLine,

    trackingOptions,

    loadingTracking,

    openTrackingModal,

    selectTracking,

    confirmSerials,

    closeTrackingModal,

    lineRequiresTracking,

    todayMySales,

    loadingTodayMySales,

    showTodayMySales,

    setShowTodayMySales,

    refreshTodayMySales,

  }

}


