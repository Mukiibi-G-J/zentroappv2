'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  Check,
  ChefHat,
  LayoutGrid,
  Loader2,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Split,
  Send,
  ShoppingBag,
  UtensilsCrossed,
  X,
} from 'lucide-react'
import { CoversPickerDialog } from '@/components/restaurant/CoversPickerDialog'
import { RestaurantCounterCheckoutDialog } from '@/components/restaurant/RestaurantCounterCheckoutDialog'
import { SeatPickerDialog } from '@/components/restaurant/SeatPickerDialog'
import { useRestaurantPOS } from '@/hooks/useRestaurantPOS'
import { usePages } from '@/hooks/usePage'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import {
  filterPosEntries,
  flattenPosTreeItems,
  posGridEntries,
  posTileClass,
  posTileStyle,
  tableStatusClass,
  orderItemStatusClass,
} from '@/lib/restaurantPosTree'

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'available', label: 'Available' },
  { value: 'occupied', label: 'Occupied' },
  { value: 'reserved', label: 'Reserved' },
]

function QuickSalesHubPanel({
  pos,
}: {
  pos: ReturnType<typeof useRestaurantPOS>
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={pos.startNewQuickSale}
          className="inline-flex items-center gap-1.5 rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Start new quick sale
        </button>
        <button
          type="button"
          onClick={() => void pos.loadOpenQuickSales()}
          disabled={pos.openQuickSalesLoading}
          className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-3 py-2 text-sm font-medium hover:bg-softBg disabled:opacity-50"
        >
          {pos.openQuickSalesLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh
        </button>
        <button
          type="button"
          onClick={pos.exitQuickSaleToTables}
          className="ml-auto inline-flex items-center gap-1 rounded-lg border border-strokeColor px-3 py-2 text-sm text-bodyText hover:bg-softBg"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to tables
        </button>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
        <h3 className="text-base font-semibold text-amber-950">Continue a quick sale</h3>
        <p className="mt-1 text-sm text-amber-900/80">
          Tap an order below to load it in POS, then add items from the <strong>Menu</strong> tab.
        </p>

        {pos.openQuickSalesLoading && pos.openQuickSales.length === 0 ? (
          <div className="flex items-center gap-2 py-8 text-sm text-amber-900">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading your quick sales…
          </div>
        ) : pos.openQuickSales.length === 0 ? (
          <p className="py-8 text-center text-sm text-amber-900/80">
            No open quick sales yet. Start a new one above.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {pos.openQuickSales.map((order) => {
              const lineCount = (order.order_items ?? []).filter(
                (line) => line.status !== 'cancelled',
              ).length
              const isActive = pos.isCounterSale && pos.selectedOrderId === order.id
              return (
                <button
                  key={order.id}
                  type="button"
                  onClick={() => void pos.resumeQuickSale(order.id)}
                  className={`flex flex-col items-start rounded-xl border-2 p-3 text-left transition hover:shadow-md ${
                    isActive
                      ? 'border-s1 bg-white ring-2 ring-s1/20'
                      : 'border-amber-200 bg-white hover:border-amber-300'
                  }`}
                >
                  <span className="text-sm font-bold text-mainTextColor">{order.no}</span>
                  <span className="mt-1 text-xs text-bodyText">
                    <span
                      className={
                        order.status === 'ready' ? 'font-semibold text-emerald-700' : ''
                      }
                    >
                      {order.status_display || order.status}
                    </span>
                    {lineCount > 0
                      ? ` · ${lineCount} item${lineCount === 1 ? '' : 's'}`
                      : ' · no items yet'}
                  </span>
                  <span className="mt-2 text-sm font-semibold text-s1">
                    {formatDecimalDisplay(order.total_amount)}
                  </span>
                  <span className="mt-2 text-[11px] text-bodyText">
                    {isActive ? 'Currently open' : 'Tap to load and continue'}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default function RestaurantPOSPage() {
  const pos = useRestaurantPOS()
  const searchParams = useSearchParams()
  const { data: pages = [] } = usePages()
  const menuBuilderPageId = pages.find((p) => p.Name === 'MenuBuilder')?.PageId
  const urlOrderLoadedRef = useRef<number | null>(null)
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const orderIdFromUrl = searchParams.get('orderId')
  useEffect(() => {
    if (!orderIdFromUrl) return
    const id = Number(orderIdFromUrl)
    if (!Number.isFinite(id) || urlOrderLoadedRef.current === id) return
    urlOrderLoadedRef.current = id
    void pos.resumeQuickSale(id)
  }, [orderIdFromUrl, pos.resumeQuickSale])

  useEffect(() => {
    if (pos.tab !== 'menu') {
      setShowSearch(false)
      setSearchQuery('')
    }
  }, [pos.tab])

  const menuEntries = useMemo(
    () => posGridEntries(pos.posTree, pos.posStack),
    [pos.posTree, pos.posStack],
  )
  const allMenuItems = useMemo(() => flattenPosTreeItems(pos.posTree), [pos.posTree])
  const visibleMenuEntries = useMemo(
    () => filterPosEntries(menuEntries, searchQuery, allMenuItems),
    [menuEntries, searchQuery, allMenuItems],
  )
  const orderTotal = pos.displayTotal
  const canPay = pos.canPayCounter || pos.canPayDineIn

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-strokeColor bg-white">
          <header className="flex shrink-0 flex-wrap items-center gap-2 border-b border-strokeColor px-3 py-2">
            {pos.sessionLabel ? (
              <button
                type="button"
                onClick={
                  pos.isCounterSale
                    ? () => void pos.backToQuickSaleHub()
                    : pos.endSession
                }
                className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-2 py-1 text-xs font-medium hover:bg-softBg"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                {pos.sessionLabel}
              </button>
            ) : null}
            {pos.tab === 'tables' ? (
              <>
                <select
                  value={pos.selectedFloorId ?? ''}
                  onChange={(e) =>
                    pos.setSelectedFloorId(e.target.value ? Number(e.target.value) : null)
                  }
                  className="rounded-lg border border-strokeColor px-2 py-1.5 text-sm"
                >
                  <option value="">All floors</option>
                  {pos.floors.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </select>
                <select
                  value={pos.statusFilter}
                  onChange={(e) => pos.setStatusFilter(e.target.value)}
                  className="rounded-lg border border-strokeColor px-2 py-1.5 text-sm"
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => void pos.openQuickSaleHub()}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-s1 px-3 py-1.5 text-sm font-medium text-white"
                >
                  <ShoppingBag className="h-4 w-4" />
                  Quick sale
                </button>
              </>
            ) : pos.tab === 'quick-sale' ? (
              <>
                <ShoppingBag className="h-4 w-4 text-s1" />
                <span className="text-sm font-semibold text-mainTextColor">Quick sales</span>
                {pos.openQuickSales.length > 0 ? (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
                    {pos.openQuickSales.length} open
                  </span>
                ) : null}
              </>
            ) : (
              <>
                {pos.posStack.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery('')
                      setShowSearch(false)
                      pos.setPosStack((s) => s.slice(0, -1))
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-2 py-1 text-xs"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back
                  </button>
                ) : null}
                {pos.menus.length > 1 ? (
                  <select
                    value={pos.activeMenu?.id ?? ''}
                    onChange={(e) => pos.setActiveMenu(pos.menus.find((m) => m.id === Number(e.target.value)) ?? null)}
                    className="rounded-lg border border-strokeColor px-2 py-1.5 text-sm"
                  >
                    {pos.menus.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-sm font-medium text-mainTextColor">
                    {pos.activeMenu?.name ?? 'Menu'}
                  </span>
                )}
                {showSearch ? (
                  <div className="ml-auto flex min-w-0 flex-1 items-center gap-2 sm:max-w-xs">
                    <input
                      autoFocus
                      type="search"
                      placeholder="Search items…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full rounded-lg border border-strokeColor px-2.5 py-1.5 text-sm outline-none focus:border-s1"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setShowSearch(false)
                        setSearchQuery('')
                      }}
                      className="rounded-lg p-1.5 text-bodyText hover:bg-softBg"
                      aria-label="Close search"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowSearch(true)}
                    className="ml-auto rounded-lg p-1.5 text-bodyText hover:bg-softBg"
                    aria-label="Search menu"
                    title="Search items"
                  >
                    <Search className="h-5 w-5" />
                  </button>
                )}
              </>
            )}
          </header>

          <div className="min-h-0 flex-1 overflow-auto p-3">
            {pos.tab === 'quick-sale' ? (
              <QuickSalesHubPanel pos={pos} />
            ) : pos.tab === 'tables' ? (
              pos.tablesLoading || pos.sessionLoading ? (
                <div className="flex h-40 items-center justify-center text-bodyText">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Loading tables…
                </div>
              ) : (
                <>
                  {pos.filteredTables.length === 0 ? (
                    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-sm text-bodyText">
                      {pos.tablesLoadError ? (
                        <>
                          <p className="font-medium text-mainTextColor">Could not load restaurant data.</p>
                          <p className="text-xs">{pos.tablesLoadError}</p>
                          <button
                            type="button"
                            onClick={() => void pos.loadTables()}
                            className="mt-2 rounded-lg border border-strokeColor px-3 py-1.5 text-xs font-medium hover:bg-softBg"
                          >
                            Retry
                          </button>
                        </>
                      ) : pos.floors.length > 0 && pos.tables.length === 0 ? (
                        <>
                          <p className="font-medium text-mainTextColor">
                            Floor{pos.floors.length === 1 ? '' : 's'} ready — no tables yet.
                          </p>
                          <p className="max-w-sm text-xs">
                            You created {pos.floors.length} floor
                            {pos.floors.length === 1 ? '' : 's'} ({pos.floors.map((f) => f.name).join(', ')}).
                            Add tables under <strong>Restaurant → Tables</strong>, assign each table to a floor,
                            then refresh this page.
                          </p>
                          <button
                            type="button"
                            onClick={() => void pos.loadTables()}
                            className="mt-2 rounded-lg border border-strokeColor px-3 py-1.5 text-xs font-medium hover:bg-softBg"
                          >
                            Refresh tables
                          </button>
                        </>
                      ) : (
                        <>
                          <p>No tables found.</p>
                          <p className="max-w-sm text-xs">
                            Create a <strong>floor</strong> and <strong>tables</strong> in Restaurant setup
                            (Tables list — link each table to your floor), or use <strong>Quick sale</strong> for
                            walk-in orders.
                          </p>
                        </>
                      )}
                    </div>
                  ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {pos.filteredTables.map((table) => (
                    <button
                      key={table.id}
                      type="button"
                      onClick={() => void pos.openTable(table.id)}
                      className={`flex min-h-20 flex-col items-center justify-center rounded-xl border-2 p-3 text-center transition hover:shadow-md ${tableStatusClass(table.status)}`}
                    >
                      <span className="text-lg font-bold">{table.table_number || table.no}</span>
                      <span className="text-xs opacity-80">{table.status_display}</span>
                      <span className="text-[11px] opacity-70">{table.capacity} seats</span>
                    </button>
                  ))}
                </div>
                  )}
                </>
              )
            ) : pos.posTreeLoading ? (
              <div className="flex h-40 items-center justify-center text-bodyText">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Loading menu…
              </div>
            ) : menuEntries.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-bodyText">
                <p className="font-medium text-mainTextColor">No menu tiles for POS.</p>
                <p className="max-w-sm text-xs">
                  Open <strong>Menu Builder</strong> to create a menu, link a location, add catalog
                  items, and build the POS grid.
                </p>
                {menuBuilderPageId ? (
                  <a
                    href={`/dashboard?page=${menuBuilderPageId}`}
                    className="mt-1 rounded-lg bg-s1 px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
                  >
                    Open Menu Builder
                  </a>
                ) : (
                  <p className="text-xs text-amber-800">
                    Menu Builder page not seeded yet — run restaurant page seed on your tenant.
                  </p>
                )}
                {pos.menus.length === 0 ? (
                  <p className="text-xs text-amber-800">No active menus loaded for this location.</p>
                ) : null}
              </div>
            ) : (
              <>
                {pos.isOrderClosed ? (
                  <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                    This check is <strong>closed and paid</strong>. You cannot add or edit items.
                    {pos.isCounterSale ? (
                      <>
                        {' '}
                        Tap <strong>← Quick sale</strong> to exit, then start a new sale.
                      </>
                    ) : (
                      <>
                        {' '}
                        Go to <strong>Tables</strong> and open the table again to start a new check.
                      </>
                    )}
                  </div>
                ) : (pos.pendingQuickSale && !pos.selectedOrderId) ||
                  pos.pendingNewCheck ||
                  pos.pendingDineInDraft ? (
                  <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
                    {pos.pendingQuickSale
                      ? 'Tap a menu item to start the quick sale.'
                      : 'Tap a menu item to create this check.'}
                  </div>
                ) : null}
                {searchQuery.trim() && visibleMenuEntries.length === 0 ? (
                  <p className="mb-3 text-center text-sm text-bodyText">
                    No items match &quot;{searchQuery.trim()}&quot;
                  </p>
                ) : null}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                {visibleMenuEntries.map((entry, idx) =>
                  entry.kind === 'group' ? (
                    <button
                      key={`g-${entry.id}`}
                      type="button"
                      onClick={() => {
                        setSearchQuery('')
                        setShowSearch(false)
                        pos.setPosStack((s) => [...s, entry.id])
                      }}
                      style={posTileStyle(entry.tile_color)}
                      className={`flex min-h-24 flex-col items-center justify-center rounded-xl p-3 text-center font-semibold shadow-sm ${posTileClass(entry.tile_color, idx)}`}
                    >
                      <span className="text-sm leading-tight">{entry.name}</span>
                    </button>
                  ) : (
                    <button
                      key={`i-${entry.id}`}
                      type="button"
                      disabled={entry.pos_out_of_stock || !pos.canModifyCheck}
                      aria-busy={pos.addingMenuItemId === entry.id}
                      onClick={() => void pos.addMenuItem(entry)}
                      style={posTileStyle(entry.tile_accent_color)}
                      className={`relative flex min-h-24 flex-col items-center justify-center rounded-xl p-2 text-center shadow-sm transition duration-150 disabled:opacity-50 ${
                        pos.addingMenuItemId === entry.id
                          ? 'ring-2 ring-white/70 brightness-95'
                          : ''
                      } ${posTileClass(entry.tile_accent_color, idx)}`}
                    >
                      <span className="text-sm font-semibold leading-tight">{entry.item_name}</span>
                      <span className="mt-1 text-xs opacity-90">
                        {formatDecimalDisplay(entry.unit_price)}
                      </span>
                      {pos.addingMenuItemId === entry.id ? (
                        <span className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/15">
                          <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        </span>
                      ) : null}
                      {entry.pos_out_of_stock ? (
                        <span className="absolute right-1 top-1 rounded bg-black/30 px-1 text-[10px]">
                          Out
                        </span>
                      ) : null}
                    </button>
                  ),
                )}
              </div>
              </>
            )}
          </div>

          <nav className="flex shrink-0 border-t border-strokeColor">
            <button
              type="button"
              onClick={() => pos.setTab('tables')}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium ${
                pos.tab === 'tables' ? 'text-s1' : 'text-bodyText'
              }`}
            >
              <LayoutGrid className="h-5 w-5" />
              Tables
            </button>
            <button
              type="button"
              onClick={() => void pos.openQuickSaleHub()}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium ${
                pos.tab === 'quick-sale' ? 'text-s1' : 'text-bodyText'
              }`}
            >
              <ShoppingBag className="h-5 w-5" />
              Quick sales
              {pos.openQuickSales.length > 0 ? (
                <span className="rounded-full bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-900">
                  {pos.openQuickSales.length}
                </span>
              ) : null}
            </button>
            <button
              type="button"
              onClick={() => pos.setTab('menu')}
              disabled={!pos.canUseMenu}
              title={
                pos.canUseMenu
                  ? 'Menu'
                  : 'Open a quick sale or table first'
              }
              className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40 ${
                pos.tab === 'menu' ? 'text-s1' : 'text-bodyText'
              }`}
            >
              <UtensilsCrossed className="h-5 w-5" />
              Menu
            </button>
          </nav>
        </section>

        <aside className="flex w-full max-w-md shrink-0 flex-col overflow-hidden rounded-xl border border-strokeColor bg-white lg:w-96">
          <header className="border-b border-strokeColor px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h2 className="font-semibold text-mainTextColor">Check</h2>
                {pos.orderDetail ? (
                  <p className="text-xs text-bodyText">
                    {pos.orderDetail.no} · {pos.orderDetail.order_type_display}
                    {pos.orderDetail.covers != null ? ` · ${pos.orderDetail.covers} covers` : ''}
                    {pos.orderDetail.customer_name ? ` · ${pos.orderDetail.customer_name}` : ''}
                  </p>
                ) : pos.hasPendingCheck ? (
                  <p className="text-xs text-bodyText">New check — add items from menu</p>
                ) : (
                  <p className="text-xs text-bodyText">
                    {pos.canUseMenu
                      ? 'Add items from the menu tab'
                      : 'Start Quick sale or open a table to begin'}
                  </p>
                )}
              </div>
              {(pos.selectedTableId != null || pos.isCounterSale) && pos.canUseMenu ? (
                <button
                  type="button"
                  onClick={pos.startNewCheck}
                  disabled={
                    pos.sessionLoading ||
                    (!pos.selectedOrderId && pos.hasPendingCheck)
                  }
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-40"
                  title="Start another check on this table"
                >
                  <Plus className="h-3 w-3" />
                  New check
                </button>
              ) : null}
            </div>
            {pos.showOrderTabs ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {pos.activeOrders.map((order) => (
                  <button
                    key={order.id}
                    type="button"
                    onClick={() => pos.selectOrder(order.id)}
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      pos.selectedOrderId === order.id && !pos.hasPendingCheck
                        ? 'bg-s1 text-white'
                        : 'border border-strokeColor bg-softBg text-bodyText hover:bg-white'
                    }`}
                  >
                    {order.no}
                  </button>
                ))}
                {pos.hasPendingCheck && pos.selectedOrderId == null ? (
                  <span className="rounded-full border border-s1 bg-s1/10 px-2 py-0.5 text-[10px] font-medium text-s1">
                    {pos.pendingQuickSale ? 'Quick sale (new)' : 'New check'}
                  </span>
                ) : null}
              </div>
            ) : null}
            {pos.checkSegments.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {pos.checkSegments.map((seg) => (
                  <button
                    key={String(seg.key)}
                    type="button"
                    onClick={() => pos.setSelectedCheckSegment(seg.key)}
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      pos.selectedCheckSegment === seg.key
                        ? 'bg-amber-600 text-white'
                        : 'border border-strokeColor bg-softBg text-bodyText hover:bg-white'
                    }`}
                  >
                    {seg.name}
                  </button>
                ))}
              </div>
            ) : null}
          </header>

          <div className="min-h-0 flex-1 overflow-auto p-3">
            {pos.isOrderClosed ? (
              <div className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-sm font-semibold text-emerald-800">This check is paid</p>
                <p className="max-w-xs text-xs text-bodyText">
                  It will not appear in the cart anymore. Start a new check for the next round.
                </p>
                <button
                  type="button"
                  onClick={pos.startNewCheck}
                  className="rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white"
                >
                  New check
                </button>
              </div>
            ) : pos.checkLines.length === 0 ? (
              <p className="py-8 text-center text-sm text-bodyText">No items yet</p>
            ) : (
              <ul className="space-y-2">
                {pos.checkLines.map((line) => {
                  const isServed = line.status === 'served'
                  const isCancelled = line.status === 'cancelled'
                  const canMarkServed = line.status === 'ready' && !isCancelled
                  const isSplitSelected = pos.splitSelectedIds.has(line.id)
                  return (
                  <li
                    key={line.id}
                    className={`flex items-start gap-2 rounded-lg border p-2 ${
                      isSplitSelected
                        ? 'border-amber-400 bg-amber-50/80'
                        : isServed
                          ? 'border-strokeColor bg-emerald-50/50'
                          : 'border-strokeColor bg-softBg/50'
                    }`}
                  >
                    {pos.splitMode && !isCancelled ? (
                      <button
                        type="button"
                        onClick={() => pos.toggleSplitLine(line.id)}
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                          isSplitSelected
                            ? 'border-amber-600 bg-amber-600 text-white'
                            : 'border-strokeColor bg-white'
                        }`}
                        aria-label="Select for split"
                      >
                        {isSplitSelected ? <Check className="h-3 w-3" /> : null}
                      </button>
                    ) : null}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p
                          className={`text-sm font-medium text-mainTextColor ${
                            isCancelled ? 'line-through opacity-60' : ''
                          }`}
                        >
                          {line.item_name}
                        </p>
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${orderItemStatusClass(line.status)}`}
                        >
                          {line.status_display}
                        </span>
                      </div>
                      <p className="text-xs text-bodyText">
                        {line.quantity} × {formatDecimalDisplay(line.unit_price)}
                        {line.seat_no != null ? ` · Seat ${line.seat_no}` : ''}
                        {line.fire_state_display && line.status === 'pending'
                          ? ` · ${line.fire_state_display}`
                          : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-1">
                      {canMarkServed && pos.canModifyCheck ? (
                        <button
                          type="button"
                          title="Mark served"
                          disabled={pos.actionLoading}
                          onClick={() => void pos.markLineServed(line.id)}
                          className="inline-flex items-center gap-0.5 rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800"
                        >
                          <Check className="h-3 w-3" />
                          Serve
                        </button>
                      ) : null}
                      {!isServed && !isCancelled && pos.canModifyCheck ? (
                        <>
                          <button
                            type="button"
                            title="Repeat"
                            disabled={pos.actionLoading}
                            onClick={() => void pos.repeatLine(line.id)}
                            className="rounded border border-strokeColor px-1.5 py-0.5 text-[10px]"
                          >
                            +
                          </button>
                          <button
                            type="button"
                            title="Remove"
                            disabled={pos.actionLoading || line.status !== 'pending'}
                            onClick={() => void pos.removeLine(line.id)}
                            className="rounded border border-red-200 px-1.5 py-0.5 text-[10px] text-red-600 disabled:opacity-40"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </>
                      ) : null}
                    </div>
                  </li>
                )})}
              </ul>
            )}
          </div>

          <footer className="space-y-2 border-t border-strokeColor p-3">
            {pos.isOrderClosed ? null : (
            <>
            <div className="flex items-center justify-between text-sm">
              <span className="text-bodyText">
                {pos.checkSegments.length > 0 && pos.selectedCheckSegment !== 'all'
                  ? 'Segment total'
                  : 'Total'}
              </span>
              <span className="text-lg font-bold text-mainTextColor">
                {formatDecimalDisplay(orderTotal)}
              </span>
            </div>
            {pos.checkSegments.length > 0 && pos.selectedCheckSegment !== 'all' ? (
              <p className="text-xs text-bodyText">
                Order total: {formatDecimalDisplay(pos.payableTotal)} — pay closes the full order
              </p>
            ) : null}
            {pos.unsentCount > 0 ? (
              <p className="text-xs text-amber-700">{pos.unsentCount} item(s) not sent</p>
            ) : null}
            {pos.readyToServeCount > 0 ? (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 p-2 text-xs text-sky-900">
                <p className="flex-1">
                  {pos.readyToServeCount} item(s) ready — tap <strong>Serve</strong> on each line or serve all.
                </p>
                <button
                  type="button"
                  disabled={pos.actionLoading || !pos.canModifyCheck}
                  onClick={() => void pos.markAllReadyAsServed()}
                  className="shrink-0 rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
                >
                  Serve all ready
                </button>
              </div>
            ) : null}
            {pos.selectedOrderId &&
            !pos.isCounterSale &&
            !pos.canPayDineIn &&
            pos.checkLines.some((l) => l.status !== 'cancelled' && l.status !== 'served') ? (
              <p className="text-xs text-bodyText">
                Mark all items <strong>Served</strong> before closing the check.
              </p>
            ) : null}
            {pos.activeLines.length === 0 && pos.allActiveLines.length > 0 ? (
              <p className="text-xs text-bodyText">No items in this segment.</p>
            ) : null}
            {pos.activeLines.length === 0 && pos.checkLines.length > 0 && pos.allActiveLines.length === 0 ? (
              <p className="text-xs text-bodyText">
                All items are cancelled — add new items or exit quick sale.
              </p>
            ) : null}
            {pos.splitMode ? (
              <div className="flex flex-wrap gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2">
                <p className="w-full text-xs text-amber-900">
                  Tap lines to select, then split to a new sub-check.
                </p>
                <button
                  type="button"
                  disabled={pos.splitSelectedIds.size === 0 || pos.actionLoading}
                  onClick={() => void pos.runSplitCheck()}
                  className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
                >
                  <Split className="h-4 w-4" />
                  Split ({pos.splitSelectedIds.size})
                </button>
                <button
                  type="button"
                  onClick={pos.cancelSplitMode}
                  className="rounded-lg border border-strokeColor px-3 py-2 text-sm"
                >
                  Cancel
                </button>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={
                  !pos.selectedOrderId ||
                  pos.activeLines.length === 0 ||
                  pos.actionLoading ||
                  pos.printingReceipt
                }
                onClick={() => void pos.printGuestCheck()}
                className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-strokeColor px-3 py-2 text-sm font-medium disabled:opacity-40"
              >
                <Printer className="h-4 w-4" />
                Print bill
              </button>
              <button
                type="button"
                disabled={!pos.selectedOrderId || pos.actionLoading || pos.printingReceipt}
                onClick={() => void pos.printKot()}
                className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-strokeColor px-3 py-2 text-sm font-medium disabled:opacity-40"
              >
                <Printer className="h-4 w-4" />
                Print KOT
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {pos.selectedOrderId && pos.allActiveLines.length > 1 && !pos.splitMode ? (
                <button
                  type="button"
                  disabled={pos.actionLoading || !pos.canModifyCheck}
                  onClick={() => pos.setSplitMode(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 disabled:opacity-40"
                >
                  <Split className="h-4 w-4" />
                  Split check
                </button>
              ) : null}
              <button
                type="button"
                disabled={
                  !pos.selectedOrderId ||
                  pos.unsentCount === 0 ||
                  pos.actionLoading ||
                  !pos.canModifyCheck ||
                  pos.activeLines.length === 0
                }
                onClick={() => void pos.fireOrder()}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
                Send
              </button>
              {canPay ? (
                <button
                  type="button"
                  onClick={() => pos.setCounterPayOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-s1 px-3 py-2 text-sm font-medium text-white"
                >
                  <ChefHat className="h-4 w-4" />
                  {pos.isCounterSale
                    ? 'Pay'
                    : pos.checkoutCheckId != null
                      ? 'Pay this check'
                      : 'Close & pay'}
                </button>
              ) : null}
            </div>
            </>
            )}
          </footer>
        </aside>
      </div>

      <CoversPickerDialog
        open={pos.coversPicker != null}
        tableLabel={pos.coversPicker?.tableLabel ?? 'table'}
        onCancel={() => pos.setCoversPicker(null)}
        onConfirm={(covers) => void pos.confirmCovers(covers)}
      />

      <SeatPickerDialog
        open={pos.pendingMenuItem != null}
        itemLabel={pos.pendingMenuItem?.item_name}
        covers={pos.currentCovers}
        onPickTable={() =>
          void pos.commitAddMenuItemLine(pos.pendingMenuItem!, null)
        }
        onPickSeat={(seat) =>
          void pos.commitAddMenuItemLine(pos.pendingMenuItem!, seat)
        }
        onAddSeat={() => void pos.addSeatFromPicker()}
        onCancel={() => pos.setPendingMenuItem(null)}
      />

      {pos.selectedOrderId ? (
        <RestaurantCounterCheckoutDialog
          open={pos.counterPayOpen}
          orderId={pos.selectedOrderId}
          total={pos.displayTotal}
          mode={pos.checkoutMode}
          initialCustomerId={pos.orderDetail?.customer ?? null}
          combineOrdersAvailable={pos.activeOrders.length > 1 && pos.checkoutCheckId == null}
          checkId={pos.checkoutCheckId}
          onClose={() => pos.setCounterPayOpen(false)}
          onSuccess={(result) => void pos.afterCheckoutSuccess(result)}
        />
      ) : null}
    </div>
  )
}
