'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { useSession } from '@/context/SessionContext'
import { useReceiptReportPrint } from '@/hooks/useReceiptReportPrint'
import { printFireTickets } from '@/lib/printFireTickets'
import { ReceiptReportId } from '@/lib/receiptReportIds'
import { restaurantService } from '@/services/restaurant.service'
import type {
  CoversChoice,
  MenuPosTreeResponse,
  OpenPosPayload,
  PosTreeMenuItem,
  RestaurantCheckSegment,
  RestaurantFloor,
  RestaurantMenu,
  RestaurantOrder,
  RestaurantOrderItem,
  RestaurantPosTab,
  RestaurantTable,
} from '@/types/restaurant'

export type CheckSegmentKey = 'all' | 'main' | number

const POS_COUNTER_DRAFT_KEY = 'zentro:restaurant-pos-counter-draft'

type CounterPosDraft = {
  waiterId: number
  pendingQuickSale: boolean
  selectedOrderId: number | null
}

function readCounterPosDraft(waiterId: number): CounterPosDraft | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(POS_COUNTER_DRAFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as CounterPosDraft
    if (parsed.waiterId !== waiterId) return null
    return parsed
  } catch {
    return null
  }
}

function writeCounterPosDraft(draft: CounterPosDraft | null) {
  if (typeof window === 'undefined') return
  if (!draft) sessionStorage.removeItem(POS_COUNTER_DRAFT_KEY)
  else sessionStorage.setItem(POS_COUNTER_DRAFT_KEY, JSON.stringify(draft))
}

function orderIsClosed(order: RestaurantOrder | null): boolean {
  if (!order) return false
  if (order.sales_invoice) return true
  if (order.status === 'completed') return true
  return false
}

function filterOpenOrders(orders: RestaurantOrder[]): RestaurantOrder[] {
  return orders.filter((o) => !orderIsClosed(o))
}

function aggregateSessionCounts(orders: RestaurantOrder[]) {
  let unsent = 0
  let fired = 0
  for (const o of orders) {
    for (const line of o.order_items ?? []) {
      if (line.status === 'pending' && (line.fire_state === undefined || line.fire_state === 'hold')) {
        unsent += 1
      }
      if (line.fire_state === 'fire') fired += 1
    }
  }
  return { unsent_items_count: unsent, fired_items_count: fired, active_checks_count: orders.length }
}

export function useRestaurantPOS() {
  const { session } = useSession()
  const { printReport, printing: printingReceipt } = useReceiptReportPrint()
  const waiterId = session?.user.id ?? null

  const [tab, setTab] = useState<RestaurantPosTab>('tables')
  const [floors, setFloors] = useState<RestaurantFloor[]>([])
  const [tables, setTables] = useState<RestaurantTable[]>([])
  const [tablesLoading, setTablesLoading] = useState(true)
  const [tablesLoadError, setTablesLoadError] = useState<string | null>(null)
  const [selectedFloorId, setSelectedFloorId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')

  const [menus, setMenus] = useState<RestaurantMenu[]>([])
  const [activeMenu, setActiveMenu] = useState<RestaurantMenu | null>(null)
  const [posTree, setPosTree] = useState<MenuPosTreeResponse | null>(null)
  const [posStack, setPosStack] = useState<number[]>([])
  const [posTreeLoading, setPosTreeLoading] = useState(false)

  const [sessionPayload, setSessionPayload] = useState<OpenPosPayload | null>(null)
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null)
  const [isCounterSale, setIsCounterSale] = useState(false)
  const [pendingQuickSale, setPendingQuickSale] = useState(false)
  const [pendingDineInDraft, setPendingDineInDraft] = useState<{
    tableId: number
    covers: CoversChoice
  } | null>(null)
  const [pendingNewCheck, setPendingNewCheck] = useState(false)
  const [pendingMenuItem, setPendingMenuItem] = useState<PosTreeMenuItem | null>(null)
  const [splitMode, setSplitMode] = useState(false)
  const [splitSelectedIds, setSplitSelectedIds] = useState<Set<number>>(new Set())
  const [selectedCheckSegment, setSelectedCheckSegment] = useState<CheckSegmentKey>('all')
  const [coversPicker, setCoversPicker] = useState<{ tableId: number; tableLabel: string } | null>(null)

  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [orderDetail, setOrderDetail] = useState<RestaurantOrder | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [addingMenuItemId, setAddingMenuItemId] = useState<number | null>(null)

  const [counterPayOpen, setCounterPayOpen] = useState(false)
  const [openQuickSales, setOpenQuickSales] = useState<RestaurantOrder[]>([])
  const [openQuickSalesLoading, setOpenQuickSalesLoading] = useState(false)
  const refreshGenerationRef = useRef(0)
  const counterRestoreAttemptedRef = useRef(false)

  const loadTables = useCallback(async () => {
    setTablesLoading(true)
    setTablesLoadError(null)
    try {
      const [floorList, tableList] = await Promise.all([
        restaurantService.getFloors(),
        restaurantService.getTables(),
      ])
      setFloors(floorList.sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name)))
      setTables(tableList)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load tables'
      setTablesLoadError(message)
      toast.error('Failed to load restaurant floors and tables')
    } finally {
      setTablesLoading(false)
    }
  }, [])

  const canUseMenu = Boolean(
    isCounterSale ||
      pendingQuickSale ||
      pendingNewCheck ||
      pendingDineInDraft ||
      selectedOrderId ||
      selectedTableId ||
      sessionPayload,
  )

  const loadMenus = useCallback(async () => {
    try {
      const list = await restaurantService.getActiveMenus()
      setMenus(list)
      setActiveMenu((prev) => prev ?? list[0] ?? null)
    } catch {
      toast.error('Could not load menus for POS')
      setMenus([])
      setActiveMenu(null)
    }
  }, [])

  const loadPosTree = useCallback(async (menuId?: number) => {
    const id = menuId ?? activeMenu?.id
    if (!id) {
      setPosTree(null)
      setPosStack([])
      return
    }
    setPosTreeLoading(true)
    try {
      const tree = await restaurantService.getMenuPosTree(id)
      setPosTree(tree)
      setPosStack([])
    } catch {
      toast.error('Could not load menu layout')
      setPosTree(null)
    } finally {
      setPosTreeLoading(false)
    }
  }, [activeMenu?.id])

  const loadOpenQuickSales = useCallback(async () => {
    if (!waiterId) {
      setOpenQuickSales([])
      return []
    }
    setOpenQuickSalesLoading(true)
    try {
      const data = await restaurantService.openCounterPos()
      const openOrders = filterOpenOrders(data.active_orders ?? [])
      setOpenQuickSales(openOrders)
      return openOrders
    } catch (err) {
      setOpenQuickSales([])
      toast.error(
        err instanceof Error ? err.message : 'Could not load open quick sales',
      )
      return []
    } finally {
      setOpenQuickSalesLoading(false)
    }
  }, [waiterId])

  useEffect(() => {
    void loadTables()
    void loadMenus()
  }, [loadTables, loadMenus])

  const applyCounterSession = useCallback(
    (data: OpenPosPayload, openOrders: RestaurantOrder[], orderId: number | null) => {
      setIsCounterSale(true)
      setPendingQuickSale(orderId == null)
      setPendingNewCheck(false)
      setPendingDineInDraft(null)
      setSelectedTableId(null)
      setSessionPayload({ ...data, active_orders: openOrders })
      setSelectedOrderId(orderId)
      if (orderId == null) {
        setOrderDetail(null)
      }
      setOpenQuickSales(openOrders)
    },
    [],
  )

  const restoreCounterSession = useCallback(async () => {
    if (!waiterId) return
    try {
      const data = await restaurantService.openCounterPos()
      const openOrders = filterOpenOrders(data.active_orders)
      setOpenQuickSales(openOrders)

      const draft = readCounterPosDraft(waiterId)
      if (!draft) return

      let mergedOrders = openOrders
      if (
        draft.selectedOrderId &&
        !openOrders.some((o) => o.id === draft.selectedOrderId)
      ) {
        try {
          const order = await restaurantService.getOrder(draft.selectedOrderId)
          if (!orderIsClosed(order) && !order.table) {
            mergedOrders = [order, ...openOrders]
          }
        } catch {
          // ignore
        }
      }

      if (
        draft.selectedOrderId &&
        mergedOrders.some((o) => o.id === draft.selectedOrderId)
      ) {
        applyCounterSession(
          { ...data, active_orders: mergedOrders },
          mergedOrders,
          draft.selectedOrderId,
        )
        return
      }

      if (draft.pendingQuickSale) {
        applyCounterSession(data, mergedOrders, null)
      }
    } catch {
      // User can load quick sales from the Tables tab.
    }
  }, [waiterId, applyCounterSession])

  useEffect(() => {
    if (!waiterId || counterRestoreAttemptedRef.current) return
    counterRestoreAttemptedRef.current = true
    void restoreCounterSession()
  }, [waiterId, restoreCounterSession])

  useEffect(() => {
    if (!waiterId || !isCounterSale) {
      writeCounterPosDraft(null)
      return
    }
    writeCounterPosDraft({
      waiterId,
      pendingQuickSale,
      selectedOrderId,
    })
  }, [waiterId, isCounterSale, pendingQuickSale, selectedOrderId])

  const hasMenuSession =
    canUseMenu

  useEffect(() => {
    if (hasMenuSession) void loadPosTree()
    else {
      setPosTree(null)
      setPosStack([])
    }
  }, [hasMenuSession, loadPosTree, activeMenu?.id])

  const refreshOrder = useCallback(
    async (orderId: number) => {
      const gen = ++refreshGenerationRef.current
      const order = await restaurantService.getOrder(orderId)
      if (gen !== refreshGenerationRef.current) return

      if (orderIsClosed(order)) {
        if (selectedTableId != null) {
          const s = await restaurantService.openPos(selectedTableId)
          if (gen !== refreshGenerationRef.current) return
          const openOrders = filterOpenOrders(s.active_orders)
          setSessionPayload({ ...s, active_orders: openOrders })
          if (selectedOrderId === orderId) {
            const next = openOrders[0] ?? null
            setSelectedOrderId(next?.id ?? null)
            setOrderDetail(next)
            if (!next) {
              setPendingDineInDraft({ tableId: selectedTableId, covers: null })
            }
          }
        } else {
          setSelectedOrderId(null)
          setOrderDetail(null)
          if (isCounterSale) setPendingQuickSale(true)
        }
        return
      }

      const lines = order.order_items ?? []
      const active = lines.filter((l) => l.status !== 'cancelled')
      const allLinesVoided = lines.length > 0 && active.length === 0

      // Only reset when lines existed and were all voided — not a brand-new empty order.
      if (allLinesVoided && !orderIsClosed(order)) {
        if (isCounterSale) {
          setSelectedOrderId(null)
          setOrderDetail(null)
          setPendingQuickSale(true)
          setSessionPayload({
            table: null,
            active_orders: [],
            ...aggregateSessionCounts([]),
            active_checks_count: 0,
          })
          toast.info('Check voided — tap an item to start a new quick sale')
          return
        }
        if (selectedTableId != null) {
          setSelectedOrderId(null)
          setOrderDetail(null)
          setPendingDineInDraft({
            tableId: selectedTableId,
            covers: order.covers ?? null,
          })
          toast.info('Check voided — tap an item to start a new check')
          return
        }
      }

      setOrderDetail(order)
      if (selectedTableId != null) {
        const s = await restaurantService.openPos(selectedTableId)
        if (gen !== refreshGenerationRef.current) return
        const openOrders = filterOpenOrders(s.active_orders)
        setSessionPayload({ ...s, active_orders: openOrders })
      } else if (isCounterSale) {
        setSessionPayload({
          table: null,
          active_orders: [order],
          ...aggregateSessionCounts([order]),
          active_checks_count: 1,
        })
        void loadOpenQuickSales()
      }
    },
    [selectedTableId, isCounterSale, loadOpenQuickSales],
  )

  useEffect(() => {
    if (selectedOrderId) void refreshOrder(selectedOrderId).catch(() => toast.error('Could not refresh order'))
  }, [selectedOrderId, refreshOrder])

  const orderClosedForPoll = orderIsClosed(orderDetail)

  // Keep line statuses in sync when kitchen updates tickets (matches Kitchen Display polling).
  useEffect(() => {
    if (!selectedOrderId || orderClosedForPoll) return
    const id = window.setInterval(() => {
      void refreshOrder(selectedOrderId).catch(() => {})
    }, 5000)
    return () => window.clearInterval(id)
  }, [selectedOrderId, refreshOrder, orderClosedForPoll])

  useEffect(() => {
    if (!selectedOrderId) return
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void refreshOrder(selectedOrderId).catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [selectedOrderId, refreshOrder])

  const filteredTables = useMemo(() => {
    let list = tables
    if (selectedFloorId != null) list = list.filter((t) => t.floor === selectedFloorId)
    if (statusFilter !== 'all') list = list.filter((t) => t.status === statusFilter)
    return list
  }, [tables, selectedFloorId, statusFilter])

  const applyTableSession = useCallback((tableId: number, data: OpenPosPayload) => {
    setIsCounterSale(false)
    setPendingQuickSale(false)
    setPendingDineInDraft(null)
    setPendingNewCheck(false)
    setPendingMenuItem(null)
    setSplitMode(false)
    setSplitSelectedIds(new Set())
    setSelectedTableId(tableId)
    const openOrders = filterOpenOrders(data.active_orders)
    setSessionPayload({ ...data, active_orders: openOrders })
    const first = openOrders[0]
    if (first) {
      setSelectedOrderId(first.id)
      setTab('menu')
    } else {
      setSelectedOrderId(null)
      setOrderDetail(null)
      setTab('menu')
    }
  }, [])

  const resumeQuickSale = useCallback(
    async (orderId: number) => {
      if (!waiterId) {
        toast.error('Sign in is required for counter sales')
        return
      }
      setSessionLoading(true)
      try {
        const order = await restaurantService.getOrder(orderId)
        if (orderIsClosed(order)) {
          toast.error('This order is closed or already paid')
          void loadOpenQuickSales()
          return
        }

        if (order.table) {
          const data = await restaurantService.openPos(order.table)
          applyTableSession(order.table, data)
          setSelectedOrderId(orderId)
          setTab('menu')
          toast.success(`Opened table order ${order.no}`)
          return
        }

        let openOrders: RestaurantOrder[] = []
        let payload: OpenPosPayload = {
          table: null,
          active_orders: [],
          active_checks_count: 0,
          unsent_items_count: 0,
          fired_items_count: 0,
        }
        try {
          const data = await restaurantService.openCounterPos()
          openOrders = filterOpenOrders(data.active_orders)
          payload = { ...data, active_orders: openOrders }
        } catch {
          // Fall back to loading this order only.
        }

        if (!openOrders.some((o) => o.id === orderId)) {
          openOrders = [order, ...openOrders.filter((o) => o.id !== orderId)]
          payload = {
            ...payload,
            active_orders: openOrders,
            ...aggregateSessionCounts(openOrders),
            active_checks_count: openOrders.length,
          }
        }

        applyCounterSession(payload, openOrders, orderId)
        setTab('menu')
        toast.success(`Loaded ${order.no} in POS`)
      } catch {
        toast.error('Could not open order in POS')
      } finally {
        setSessionLoading(false)
      }
    },
    [waiterId, applyCounterSession, applyTableSession, loadOpenQuickSales],
  )

  const openTable = useCallback(
    async (tableId: number) => {
      if (!waiterId) {
        toast.error('Sign in is required to open a table')
        return
      }
      setSessionLoading(true)
      try {
        const data = await restaurantService.openPos(tableId)
        if (data.active_orders.length > 0) {
          applyTableSession(tableId, data)
          return
        }
        const label =
          data.table?.table_number?.trim() || `Table #${tableId}`
        setCoversPicker({ tableId, tableLabel: label })
      } catch {
        toast.error('Could not open table')
      } finally {
        setSessionLoading(false)
      }
    },
    [waiterId, applyTableSession],
  )

  const confirmCovers = useCallback(
    async (covers: CoversChoice) => {
      if (!coversPicker || !waiterId) return
      const { tableId } = coversPicker
      setCoversPicker(null)
      setSessionLoading(true)
      try {
        setPendingDineInDraft({ tableId, covers })
        const data = await restaurantService.openPos(tableId)
        setIsCounterSale(false)
        setSelectedTableId(tableId)
        setSessionPayload(data)
        setSelectedOrderId(null)
        setOrderDetail(null)
        setTab('menu')
        toast.success('Select menu items to start this check')
      } catch {
        setPendingDineInDraft(null)
        toast.error('Could not open table')
      } finally {
        setSessionLoading(false)
      }
    },
    [coversPicker, waiterId],
  )

  const startNewQuickSale = useCallback(() => {
    if (!waiterId) {
      toast.error('Sign in is required for counter sales')
      return
    }
    setIsCounterSale(true)
    setPendingQuickSale(true)
    setPendingDineInDraft(null)
    setSelectedTableId(null)
    setSelectedOrderId(null)
    setOrderDetail(null)
    setSessionPayload({
      table: null,
      active_orders: [],
      ...aggregateSessionCounts([]),
      active_checks_count: 0,
    })
    setTab('menu')
    toast.success('New quick sale — add an item to start the order')
  }, [waiterId])

  const openQuickSaleHub = useCallback(async () => {
    if (!waiterId) {
      toast.error('Sign in is required for counter sales')
      return
    }
    setTab('quick-sale')
    await loadOpenQuickSales()
  }, [waiterId, loadOpenQuickSales])

  const backToQuickSaleHub = useCallback(async () => {
    setTab('quick-sale')
    await loadOpenQuickSales()
  }, [loadOpenQuickSales])

  const exitQuickSaleToTables = useCallback(() => {
    refreshGenerationRef.current += 1
    writeCounterPosDraft(null)
    setSessionPayload(null)
    setSelectedTableId(null)
    setSelectedOrderId(null)
    setOrderDetail(null)
    setIsCounterSale(false)
    setPendingQuickSale(false)
    setPendingDineInDraft(null)
    setPendingNewCheck(false)
    setPendingMenuItem(null)
    setSplitMode(false)
    setSplitSelectedIds(new Set())
    setSelectedCheckSegment('all')
    setTab('tables')
    void loadTables()
    void loadOpenQuickSales()
  }, [loadTables, loadOpenQuickSales])

  const endSession = useCallback(() => {
    refreshGenerationRef.current += 1
    writeCounterPosDraft(null)
    setSessionPayload(null)
    setSelectedTableId(null)
    setSelectedOrderId(null)
    setOrderDetail(null)
    setIsCounterSale(false)
    setPendingQuickSale(false)
    setPendingDineInDraft(null)
    setPendingNewCheck(false)
    setPendingMenuItem(null)
    setSplitMode(false)
    setSplitSelectedIds(new Set())
    setSelectedCheckSegment('all')
    setTab('tables')
    void loadTables()
    void loadOpenQuickSales()
  }, [loadTables, loadOpenQuickSales])

  const afterCheckoutSuccess = useCallback(
    async (result?: { orderCompleted: boolean }) => {
      refreshGenerationRef.current += 1
      setCounterPayOpen(false)

      const fullyClosed = result?.orderCompleted !== false

      if (isCounterSale || selectedTableId == null) {
        endSession()
        return
      }

      // Partial split settle — keep the same order open with remaining unpaid lines.
      if (!fullyClosed && selectedOrderId != null) {
        setSessionLoading(true)
        try {
          const data = await restaurantService.openPos(selectedTableId)
          const openOrders = filterOpenOrders(data.active_orders)
          setSessionPayload({ ...data, active_orders: openOrders })
          const refreshed = openOrders.find((o) => o.id === selectedOrderId)
          if (refreshed) {
            setOrderDetail(refreshed)
            setSelectedCheckSegment('all')
            setSplitMode(false)
            setSplitSelectedIds(new Set())
          } else {
            setSelectedOrderId(null)
            setOrderDetail(null)
            setPendingDineInDraft({ tableId: selectedTableId, covers: null })
          }
          void loadTables()
        } catch {
          endSession()
        } finally {
          setSessionLoading(false)
        }
        return
      }

      setSessionLoading(true)
      try {
        const data = await restaurantService.openPos(selectedTableId)
        const openOrders = filterOpenOrders(data.active_orders)
        setSessionPayload({ ...data, active_orders: openOrders })
        setSelectedOrderId(null)
        setOrderDetail(null)
        setPendingNewCheck(false)
        setPendingMenuItem(null)
        setSplitMode(false)
        setSplitSelectedIds(new Set())
        setSelectedCheckSegment('all')
        setPendingDineInDraft({ tableId: selectedTableId, covers: null })
        setTab('menu')
        toast.success('Payment complete — add items to start a new check')
        void loadTables()
      } catch {
        endSession()
      } finally {
        setSessionLoading(false)
      }
    },
    [isCounterSale, selectedTableId, selectedOrderId, endSession, loadTables],
  )

  const startNewCheck = useCallback(() => {
    if (!waiterId) {
      toast.error('Sign in is required to start a new check')
      return
    }
    if (!isCounterSale && selectedTableId == null) {
      return
    }
    if (
      !selectedOrderId &&
      (pendingQuickSale || pendingNewCheck || pendingDineInDraft != null)
    ) {
      toast.warning('Add an item to this check or select another one')
      return
    }
    setPendingNewCheck(true)
    setPendingQuickSale(false)
    setPendingDineInDraft(null)
    setPendingMenuItem(null)
    setSelectedOrderId(null)
    setOrderDetail(null)
    setSplitMode(false)
    setSplitSelectedIds(new Set())
    setSelectedCheckSegment('all')
    setTab('menu')
    toast.success('Select items to create this check')
  }, [
    waiterId,
    isCounterSale,
    selectedTableId,
    selectedOrderId,
    pendingQuickSale,
    pendingNewCheck,
    pendingDineInDraft,
  ])

  const commitAddMenuItemLine = useCallback(
    async (line: PosTreeMenuItem, seatNo: number | null) => {
      setPendingMenuItem(null)
      if (!waiterId) {
        toast.error('Sign in is required')
        return
      }
      if (orderIsClosed(orderDetail)) {
        toast.error('This check is closed')
        return
      }
      const itemNo = line.item_no
      if (!itemNo) {
        toast.error('This menu tile is not linked to an item')
        return
      }
      const allowPending =
        pendingQuickSale ||
        pendingNewCheck ||
        pendingDineInDraft != null
      if (!selectedOrderId && !allowPending) {
        toast.error('Open a table or start quick sale first')
        return
      }
      // Scope busy UI to this tile only — do not set actionLoading here or the
      // whole menu grid greys out (disabled:opacity-50) on every add-to-cart.
      setAddingMenuItemId(line.id)
      try {
        let orderId = selectedOrderId
        let createdNewOrder = false
        if (orderId == null) {
          if (pendingQuickSale && isCounterSale) {
            const created = await restaurantService.createOrder({
              order_type: 'takeout',
              waiter: waiterId,
              covers: null,
            })
            orderId = created.id
            createdNewOrder = true
            setPendingQuickSale(false)
            setPendingNewCheck(false)
          } else if (pendingNewCheck && isCounterSale) {
            const created = await restaurantService.createOrder({
              order_type: 'takeout',
              waiter: waiterId,
              covers: null,
            })
            orderId = created.id
            createdNewOrder = true
            setPendingNewCheck(false)
          } else if (pendingNewCheck && selectedTableId != null) {
            const created = await restaurantService.createOrder({
              table: selectedTableId,
              waiter: waiterId,
              order_type: 'dine_in',
              covers: null,
            })
            orderId = created.id
            createdNewOrder = true
            setPendingNewCheck(false)
          } else if (pendingDineInDraft) {
            const { tableId, covers } = pendingDineInDraft
            const created = await restaurantService.createOrder({
              table: tableId,
              waiter: waiterId,
              order_type: 'dine_in',
              covers,
            })
            orderId = created.id
            createdNewOrder = true
            setPendingDineInDraft(null)
          } else {
            return
          }
        }
        await restaurantService.addItemsToOrder(orderId, [
          {
            item: itemNo,
            quantity: 1,
            unit_price: Number(line.unit_price ?? 0),
            seat_no: seatNo,
          },
        ])
        if (createdNewOrder) {
          setSelectedOrderId(orderId)
        }
        await refreshOrder(orderId)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Could not add item')
      } finally {
        setAddingMenuItemId(null)
      }
    },
    [
      waiterId,
      orderDetail,
      selectedOrderId,
      pendingQuickSale,
      pendingNewCheck,
      pendingDineInDraft,
      isCounterSale,
      selectedTableId,
      refreshOrder,
    ],
  )

  const addMenuItem = useCallback(
    async (line: PosTreeMenuItem) => {
      if (addingMenuItemId != null || actionLoading) {
        return
      }
      if (!waiterId) {
        toast.error('Sign in is required')
        return
      }
      if (orderIsClosed(orderDetail)) {
        toast.error('This check is closed — start a new quick sale')
        return
      }
      const itemNo = line.item_no
      if (!itemNo) {
        toast.error('This menu tile is not linked to an item')
        return
      }
      const allowPending =
        pendingQuickSale ||
        pendingNewCheck ||
        pendingDineInDraft != null
      if (!selectedOrderId && !allowPending) {
        toast.error('Open a table or start quick sale first')
        return
      }
      if (!isCounterSale && (selectedTableId != null || pendingDineInDraft != null)) {
        setPendingMenuItem(line)
        return
      }
      await commitAddMenuItemLine(line, null)
    },
    [
      addingMenuItemId,
      actionLoading,
      waiterId,
      orderDetail,
      selectedOrderId,
      pendingQuickSale,
      pendingNewCheck,
      pendingDineInDraft,
      isCounterSale,
      selectedTableId,
      commitAddMenuItemLine,
    ],
  )

  const addSeatFromPicker = useCallback(async () => {
    if (!selectedOrderId) {
      if (pendingDineInDraft) {
        const next = (pendingDineInDraft.covers ?? 0) + 1
        setPendingDineInDraft({ ...pendingDineInDraft, covers: next })
        toast.success(`Covers set to ${next}`)
        return
      }
      toast.warning('Start the check first, then add seats')
      return
    }
    const next = (orderDetail?.covers ?? 0) + 1
    setActionLoading(true)
    try {
      await restaurantService.updateOrder(selectedOrderId, { covers: next })
      await refreshOrder(selectedOrderId)
      toast.success(`Covers set to ${next}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not add seat')
    } finally {
      setActionLoading(false)
    }
  }, [selectedOrderId, orderDetail?.covers, pendingDineInDraft, refreshOrder])

  const runSplitCheck = useCallback(async () => {
    if (!selectedOrderId) return
    const ids = Array.from(splitSelectedIds)
    if (!ids.length) {
      toast.warning('Select at least one line to split')
      return
    }
    setActionLoading(true)
    try {
      const targetName =
        splitSelectedIds.size === 1 ? 'Split check' : `Split check (${ids.length} items)`
      await restaurantService.splitCheck(selectedOrderId, {
        item_ids: ids,
        target_name: targetName,
      })
      setSplitMode(false)
      setSplitSelectedIds(new Set())
      setSelectedCheckSegment('all')
      toast.success('New sub-check created')
      await refreshOrder(selectedOrderId)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Split failed')
    } finally {
      setActionLoading(false)
    }
  }, [selectedOrderId, splitSelectedIds, refreshOrder])

  const toggleSplitLine = useCallback((lineId: number) => {
    setSplitSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(lineId)) next.delete(lineId)
      else next.add(lineId)
      return next
    })
  }, [])

  const cancelSplitMode = useCallback(() => {
    setSplitMode(false)
    setSplitSelectedIds(new Set())
  }, [])

  const fireOrder = useCallback(async () => {
    if (!selectedOrderId) return
    if (orderIsClosed(orderDetail)) {
      toast.error('This check is closed')
      return
    }
    setActionLoading(true)
    try {
      const res = await restaurantService.fireOrder(selectedOrderId)
      toast.success(res.message || 'Sent to kitchen')
      try {
        await printFireTickets(
          selectedOrderId,
          res.kitchen_order_ticket,
          res.bar_order_ticket,
        )
      } catch (printErr) {
        console.error(printErr)
        toast.warning('Sent to kitchen, but ticket printing failed')
      }
      await refreshOrder(selectedOrderId)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Send failed')
    } finally {
      setActionLoading(false)
    }
  }, [selectedOrderId, orderDetail, refreshOrder])

  const printKot = useCallback(async () => {
    if (!selectedOrderId) return
    try {
      await printReport(ReceiptReportId.KITCHEN_ORDER, { order_id: selectedOrderId })
      toast.success('KOT printed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'KOT print failed')
    }
  }, [selectedOrderId, printReport])

  const printGuestCheck = useCallback(async () => {
    if (!selectedOrderId) return
    try {
      await printReport(ReceiptReportId.GUEST_CHECK, { order_id: selectedOrderId })
      toast.success('Guest check printed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Print bill failed')
    }
  }, [selectedOrderId, printReport])

  const removeLine = useCallback(
    async (itemId: number) => {
      if (!selectedOrderId) return
      setActionLoading(true)
      try {
        await restaurantService.deleteOrCancelOrderItem(itemId)
        await refreshOrder(selectedOrderId)
      } catch {
        toast.error('Could not remove line')
      } finally {
        setActionLoading(false)
      }
    },
    [selectedOrderId, refreshOrder],
  )

  const repeatLine = useCallback(
    async (itemId: number) => {
      if (!selectedOrderId) return
      setActionLoading(true)
      try {
        await restaurantService.repeatOrderItem(itemId)
        await refreshOrder(selectedOrderId)
      } catch {
        toast.error('Could not repeat line')
      } finally {
        setActionLoading(false)
      }
    },
    [selectedOrderId, refreshOrder],
  )

  const markLineServed = useCallback(
    async (itemId: number) => {
      if (!selectedOrderId) return
      setActionLoading(true)
      try {
        await restaurantService.updateOrderItemStatus(itemId, 'served')
        toast.success('Item marked as served')
        await refreshOrder(selectedOrderId)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Could not mark served')
      } finally {
        setActionLoading(false)
      }
    },
    [selectedOrderId, refreshOrder],
  )

  const markAllReadyAsServed = useCallback(async () => {
    if (!selectedOrderId) return
    const readyIds = (orderDetail?.order_items ?? [])
      .filter((line) => line.status === 'ready')
      .map((line) => line.id)
    if (!readyIds.length) {
      toast.warning('No ready items to serve')
      return
    }
    setActionLoading(true)
    try {
      for (const itemId of readyIds) {
        await restaurantService.updateOrderItemStatus(itemId, 'served')
      }
      toast.success(`Marked ${readyIds.length} item(s) as served`)
      await refreshOrder(selectedOrderId)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not mark served')
    } finally {
      setActionLoading(false)
    }
  }, [selectedOrderId, orderDetail?.order_items, refreshOrder])

  const selectOrder = useCallback((orderId: number) => {
    setSelectedOrderId(orderId)
    setPendingNewCheck(false)
    setPendingMenuItem(null)
    setSplitMode(false)
    setSplitSelectedIds(new Set())
    setSelectedCheckSegment('all')
    setTab('menu')
  }, [])

  const currentCovers: CoversChoice = useMemo(() => {
    if (pendingDineInDraft) return pendingDineInDraft.covers
    if (orderDetail?.covers != null) return orderDetail.covers
    return null
  }, [pendingDineInDraft, orderDetail?.covers])

  const checkSegments = useMemo((): Array<{ key: CheckSegmentKey; name: string }> => {
    const checks: RestaurantCheckSegment[] = orderDetail?.active_checks ?? []
    if (checks.length === 0) return []
    const segments: Array<{ key: CheckSegmentKey; name: string }> = [
      { key: 'all', name: 'All' },
      { key: 'main', name: 'Main' },
    ]
    for (const c of checks) {
      segments.push({ key: c.id, name: c.name })
    }
    return segments
  }, [orderDetail?.active_checks])

  const unpaidCheckIds = useMemo(() => {
    return new Set((orderDetail?.active_checks ?? []).map((c) => c.id))
  }, [orderDetail?.active_checks])

  const isUnpaidLine = useCallback(
    (line: RestaurantOrderItem) => {
      if (line.status === 'cancelled') return false
      // Settled split segments drop out of active_checks; hide those lines from pay UI.
      if (line.restaurant_check != null && !unpaidCheckIds.has(line.restaurant_check)) {
        return false
      }
      return true
    },
    [unpaidCheckIds],
  )

  const filterLineBySegment = useCallback(
    (line: RestaurantOrderItem, segment: CheckSegmentKey) => {
      if (!isUnpaidLine(line)) return false
      if (segment === 'all') return true
      if (segment === 'main') return line.restaurant_check == null
      return line.restaurant_check === segment
    },
    [isUnpaidLine],
  )

  const sessionLabel = useMemo(() => {
    if (isCounterSale) return 'Quick sale'
    if (sessionPayload?.table) {
      return `Table ${sessionPayload.table.table_number || sessionPayload.table.no}`
    }
    if (selectedTableId) return `Table #${selectedTableId}`
    return null
  }, [isCounterSale, sessionPayload, selectedTableId])

  const allCheckLines = orderDetail?.order_items ?? []
  const unpaidCheckLines = useMemo(
    () => allCheckLines.filter((l) => isUnpaidLine(l)),
    [allCheckLines, isUnpaidLine],
  )
  const checkLines = useMemo(
    () =>
      checkSegments.length > 0
        ? allCheckLines.filter((l) => filterLineBySegment(l, selectedCheckSegment))
        : unpaidCheckLines,
    [
      allCheckLines,
      checkSegments.length,
      filterLineBySegment,
      selectedCheckSegment,
      unpaidCheckLines,
    ],
  )
  const isOrderClosed = orderIsClosed(orderDetail)
  const canModifyCheck = canUseMenu && !isOrderClosed
  const activeOrders = sessionPayload?.active_orders ?? []
  const hasPendingCheck =
    pendingQuickSale || pendingNewCheck || pendingDineInDraft != null
  const showOrderTabs = activeOrders.length > 1 || hasPendingCheck
  const unsentCount = unpaidCheckLines.filter(
    (l) => l.status === 'pending' && (l.fire_state === undefined || l.fire_state === 'hold'),
  ).length
  const readyToServeCount = unpaidCheckLines.filter((l) => l.status === 'ready').length
  const activeLines = checkLines.filter((l) => l.status !== 'cancelled')
  const allActiveLines = unpaidCheckLines.filter((l) => l.status !== 'cancelled')
  const payableTotal = allActiveLines.reduce(
    (sum, line) => sum + Number(line.total_price ?? line.quantity * line.unit_price),
    0,
  )
  const segmentTotal = activeLines.reduce(
    (sum, line) => sum + Number(line.total_price ?? line.quantity * line.unit_price),
    0,
  )
  const payingSegment = checkSegments.length > 0 && selectedCheckSegment !== 'all'
  const displayTotal = payingSegment ? segmentTotal : payableTotal
  const checkoutCheckId: number | 'main' | null = payingSegment
    ? selectedCheckSegment === 'main'
      ? 'main'
      : typeof selectedCheckSegment === 'number'
        ? selectedCheckSegment
        : null
    : null
  const segmentAllServed =
    activeLines.length > 0 && activeLines.every((l) => l.status === 'served')
  const allActiveServed =
    allActiveLines.length > 0 && allActiveLines.every((l) => l.status === 'served')
  const canPayDineIn =
    !isCounterSale &&
    !isOrderClosed &&
    selectedOrderId != null &&
    (payingSegment
      ? activeLines.length > 0 &&
        segmentTotal > 0 &&
        (orderDetail?.status === 'served' || segmentAllServed)
      : allActiveLines.length > 0 &&
        payableTotal > 0 &&
        (orderDetail?.status === 'served' || allActiveServed))
  const canPayCounter =
    isCounterSale &&
    selectedOrderId != null &&
    allActiveLines.length > 0 &&
    payableTotal > 0
  const checkoutMode: 'counter' | 'dine_in' = isCounterSale ? 'counter' : 'dine_in'

  return {
    tab,
    setTab,
    floors,
    tables,
    tablesLoading,
    tablesLoadError,
    loadTables,
    filteredTables,
    selectedFloorId,
    setSelectedFloorId,
    statusFilter,
    setStatusFilter,
    menus,
    activeMenu,
    setActiveMenu,
    posTree,
    posStack,
    setPosStack,
    posTreeLoading,
    sessionPayload,
    sessionLabel,
    sessionLoading,
    selectedTableId,
    actionLoading,
    addingMenuItemId,
    selectedOrderId,
    orderDetail,
    checkLines,
    unsentCount,
    readyToServeCount,
    activeOrders,
    allActiveServed,
    canPayDineIn,
    canPayCounter,
    payableTotal,
    activeLines,
    checkoutMode,
    isCounterSale,
    pendingQuickSale,
    pendingDineInDraft,
    pendingNewCheck,
    pendingMenuItem,
    currentCovers,
    coversPicker,
    setCoversPicker,
    counterPayOpen,
    setCounterPayOpen,
    openQuickSales,
    openQuickSalesLoading,
    loadOpenQuickSales,
    resumeQuickSale,
    openTable,
    confirmCovers,
    startNewQuickSale,
    openQuickSaleHub,
    backToQuickSaleHub,
    exitQuickSaleToTables,
    startNewCheck,
    endSession,
    afterCheckoutSuccess,
    addMenuItem,
    commitAddMenuItemLine,
    addSeatFromPicker,
    setPendingMenuItem,
    fireOrder,
    printKot,
    printGuestCheck,
    printingReceipt,
    removeLine,
    repeatLine,
    markLineServed,
    markAllReadyAsServed,
    selectOrder,
    refreshOrder,
    canUseMenu,
    isOrderClosed,
    canModifyCheck,
    hasPendingCheck,
    showOrderTabs,
    checkSegments,
    selectedCheckSegment,
    setSelectedCheckSegment,
    splitMode,
    setSplitMode,
    splitSelectedIds,
    toggleSplitLine,
    runSplitCheck,
    cancelSplitMode,
    displayTotal,
    checkoutCheckId,
    allActiveLines,
  }
}
