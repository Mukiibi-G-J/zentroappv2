'use client'



import { useCallback, useEffect, useMemo, useState } from 'react'

import { usePageDataInfinite } from '@/hooks/usePageData'

import { usePages } from '@/hooks/usePage'

import {

  fetchAllItemLedgerEntries,

  getItemByNo,

  itemRequiresTracking,

  pickAvailableLots,

} from '@/services/items.service'

import { salesService } from '@/services/sales.service'

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



const MAX_DRAFTS = 3



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



function validateTrackingLines(cart: POSCartLine[]): string | null {

  const missing = cart.filter(

    (line) => lineRequiresTracking(line) && !line.selectedLotNo?.trim(),

  )

  if (!missing.length) return null

  const names = missing.map((l) => l.name).join(', ')

  return `Select a lot for: ${names}`

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

  return {

    ...raw,

    enable_line_discounts: raw.enable_line_discounts ?? raw.line_discounts_enabled ?? false,

    allow_price_editing:

      raw.allow_price_editing ?? (raw.disable_price_editing != null ? !raw.disable_price_editing : true),

  }

}



function buildSalePayload(

  cart: POSCartLine[],

  customer: POSCustomer,

  paymentMethod: POSPaymentMethod | null,

  status: 'Open' | 'Draft',

  salesSetup: POSSalesSetup,

  amountReceived: number,

  subtotal: number,

) {

  const requiresTender = paymentMethod?.requires_amount_received !== false

  return {

    customer: customer.id,

    customer_name: customer.name,

    document_date: todayIsoDate(),

    status,

    amount_received: status === 'Open' && requiresTender ? amountReceived : 0,

    change_amount:

      status === 'Open' && requiresTender ? Math.max(0, amountReceived - subtotal) : 0,

    payment_method: paymentMethod?.id,

    invoice_discount_type: null,

    invoice_discount_amount: '0',

    invoice_discount_percentage: '0',

    lines: cart.map((line, index) => ({

      id: index + 1,

      item: line.no,

      item_no: line.no,

      item_name: line.name,

      quantity: String(line.quantity),

      unit_price: String(line.unitPrice),

      total_amount: String(line.quantity * line.unitPrice - line.lineDiscountAmount),

      line_discount_amount: String(

        salesSetup.enable_line_discounts ? line.lineDiscountAmount : 0,

      ),

      unit_of_measure: line.unitOfMeasure,

      tracking_code: line.selectedLotNo ?? '',

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

  const [companyInfo, setCompanyInfo] = useState<POSCompanyInfo | null>(null)

  const [amountReceived, setAmountReceived] = useState(0)

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

    undefined,

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

        return sum + gross - (line.lineDiscountAmount || 0)

      }, 0),

    [cart],

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

      const [customerRows, methods, setup, favData, company] = await Promise.all([

        salesService.getCustomers(),

        salesService.getPaymentMethods(),

        salesService.getSalesSetup(),

        salesService.getFavorites().catch(() => ({ slots: [], min_slots: 4 })),

        salesService.getCompanyInfo(),

      ])

      setCustomers(customerRows)

      setPaymentMethods(methods)

      setSalesSetup(normalizeSetup(setup))

      setCompanyInfo(company)



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

      const summary = await salesService.getSalesUserSummary({

        status: 'Posted',

        date_range_after: today,

        date_range_before: today,

      })

      const mine = summary.users?.find((row) => row.user_id === userId)

      setTodayMySales(Number(mine?.total_sales ?? 0))

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



  const removeLine = useCallback((clientId: string) => {

    setCart((prev) => prev.filter((l) => l.clientId !== clientId))

  }, [])



  const clearCart = useCallback(() => {

    setCart([])

    setAmountReceived(0)

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

      setTrackingOptions(pickAvailableLots(entries))

    } catch (e) {

      setError(e instanceof Error ? e.message : 'Failed to load lots')

      setTrackingOptions([])

    } finally {

      setLoadingTracking(false)

    }

  }, [cart])



  const selectTracking = useCallback((lotNo: string) => {

    if (!trackingClientId) return

    setCart((prev) =>

      prev.map((l) =>

        l.clientId === trackingClientId ? { ...l, selectedLotNo: lotNo } : l,

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

    setAmountReceived(subtotal)

    setCheckoutOpen(true)

  }, [cart, subtotal])



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

          subtotal,

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

    cart,

    clearCart,

    salesSetup,

    selectedCustomer,

    selectedPaymentMethod,

    subtotal,

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

    if (requiresTender && amountReceived < subtotal) {

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

        subtotal,

      )

      const created = await salesService.createSale(payload)

      createdId = created.id

      const postResult = await salesService.postInvoice(created.id)

      setCompletedSale({

        id: created.id,

        invoice_no: postResult.invoice_no ?? created.invoice_no,

        total_amount: subtotal,

        amount_received: requiresTender ? amountReceived : 0,

        change_amount: requiresTender ? Math.max(0, amountReceived - subtotal) : 0,

        customer_name: selectedCustomer.name,

        customer_no: selectedCustomer.no,

        payment_method_name: selectedPaymentMethod.description,

        payment_method_details: {

          id: selectedPaymentMethod.id,

          code: selectedPaymentMethod.code,

          description: selectedPaymentMethod.description,

          requires_amount_received: selectedPaymentMethod.requires_amount_received !== false,

        },

        document_date: todayIsoDate(),

        created_at: new Date().toISOString(),

        vat_enabled: salesSetup.vat_enabled,

        vat_amount: Number(postResult.invoice?.total_vat_amount ?? 0),

        total_excl_vat:

          salesSetup.vat_enabled && Number(postResult.invoice?.total_vat_amount ?? 0) > 0

            ? subtotal - Number(postResult.invoice?.total_vat_amount ?? 0)

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

    cart,

    clearCart,

    salesSetup,

    selectedCustomer,

    selectedPaymentMethod,

    subtotal,

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

    customers,

    selectedCustomer,

    setSelectedCustomer,

    refreshCustomers,

    paymentMethods,

    selectedPaymentMethod,

    setSelectedPaymentMethod,

    amountReceived,

    setAmountReceived,

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

    closeTrackingModal,

    lineRequiresTracking,

    todayMySales,

    loadingTodayMySales,

    showTodayMySales,

    setShowTodayMySales,

    refreshTodayMySales,

  }

}


