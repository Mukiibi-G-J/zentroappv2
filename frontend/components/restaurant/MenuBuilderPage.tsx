'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  BookOpen,
  ChevronLeft,
  LayoutGrid,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { searchItems } from '@/services/items.service'
import { restaurantService } from '@/services/restaurant.service'
import { readBranchSession } from '@/lib/branchSession'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import { getCardRecordPath } from '@/lib/pageRoutes'
import { posGridEntries, posTileClass, posTileStyle } from '@/lib/restaurantPosTree'
import { usePages } from '@/hooks/usePage'
import type {
  InventoryLocation,
  MenuPosTreeResponse,
  RestaurantMenu,
  RestaurantMenuItem,
} from '@/types/restaurant'

type BuilderTab = 'setup' | 'catalog' | 'preview'

const TABS: { id: BuilderTab; label: string; icon: typeof BookOpen }[] = [
  { id: 'setup', label: 'Setup', icon: BookOpen },
  { id: 'catalog', label: 'Catalog', icon: Search },
  { id: 'preview', label: 'POS preview', icon: LayoutGrid },
]

function defaultLocationIdForBranch(
  locations: InventoryLocation[],
): number | '' {
  const branch =
    readBranchSession().activeBranch ?? readBranchSession().assignedBranch
  const code = branch?.code?.trim().toLowerCase()
  if (!code) return locations[0]?.id ?? ''
  const match = locations.find((loc) => loc.code.trim().toLowerCase() === code)
  return match?.id ?? locations[0]?.id ?? ''
}

export default function MenuBuilderPage() {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const [tab, setTab] = useState<BuilderTab>('setup')
  const [menus, setMenus] = useState<RestaurantMenu[]>([])
  const [menusLoading, setMenusLoading] = useState(true)
  const [menuId, setMenuId] = useState<number | null>(null)
  const [locations, setLocations] = useState<InventoryLocation[]>([])
  const [linkedLocationIds, setLinkedLocationIds] = useState<number[]>([])
  const [catalog, setCatalog] = useState<RestaurantMenuItem[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [itemSearch, setItemSearch] = useState('')
  const [itemHits, setItemHits] = useState<
    Array<{ no: string; item_name: string; unit_price: number }>
  >([])
  const [searching, setSearching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [previewTree, setPreviewTree] = useState<MenuPosTreeResponse | null>(null)
  const [previewStack, setPreviewStack] = useState<number[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)

  const [newMenuName, setNewMenuName] = useState('')
  const [newMenuLocationId, setNewMenuLocationId] = useState<number | ''>('')

  const selectedMenu = useMemo(
    () => menus.find((m) => m.id === menuId) ?? null,
    [menus, menuId],
  )

  const previewEntries = useMemo(
    () => posGridEntries(previewTree, previewStack),
    [previewTree, previewStack],
  )
  const previewCount = previewTree ? posGridEntries(previewTree, []).length : null

  const loadMenus = useCallback(async () => {
    setMenusLoading(true)
    try {
      const list = await restaurantService.getMenus()
      setMenus(list)
      setMenuId((prev) => prev ?? list[0]?.id ?? null)
    } catch {
      toast.error('Could not load menus')
    } finally {
      setMenusLoading(false)
    }
  }, [])

  const loadLocations = useCallback(async () => {
    try {
      const list = await restaurantService.getLocations()
      setLocations(list)
      setNewMenuLocationId((prev) => (prev === '' ? defaultLocationIdForBranch(list) : prev))
    } catch {
      toast.error('Could not load inventory locations')
    }
  }, [])

  const loadMenuLinks = useCallback(async (id: number) => {
    try {
      const links = await restaurantService.getMenuLocations(id)
      setLinkedLocationIds(links.map((l) => l.location))
    } catch {
      setLinkedLocationIds([])
    }
  }, [])

  const loadCatalog = useCallback(async (id: number) => {
    setCatalogLoading(true)
    try {
      const items = await restaurantService.getMenuItems({ menu: id })
      setCatalog(items)
    } catch {
      toast.error('Could not load menu catalog')
      setCatalog([])
    } finally {
      setCatalogLoading(false)
    }
  }, [])

  const refreshPreview = useCallback(async (id: number) => {
    setPreviewLoading(true)
    try {
      const tree = await restaurantService.getMenuPosTree(id)
      setPreviewTree(tree)
      setPreviewStack([])
    } catch {
      setPreviewTree(null)
      setPreviewStack([])
    } finally {
      setPreviewLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMenus()
    void loadLocations()
  }, [loadMenus, loadLocations])

  useEffect(() => {
    if (!menuId) return
    void loadMenuLinks(menuId)
    void loadCatalog(menuId)
    void refreshPreview(menuId)
  }, [menuId, loadMenuLinks, loadCatalog, refreshPreview])

  useEffect(() => {
    const q = itemSearch.trim()
    if (q.length < 2) {
      setItemHits([])
      return
    }
    const t = window.setTimeout(() => {
      setSearching(true)
      void searchItems(q, 15)
        .then((rows) =>
          setItemHits(
            rows.map((r) => ({
              no: r.no,
              item_name: r.item_name,
              unit_price: r.unit_price,
            })),
          ),
        )
        .catch(() => setItemHits([]))
        .finally(() => setSearching(false))
    }, 300)
    return () => window.clearTimeout(t)
  }, [itemSearch])

  const handleCreateMenu = async () => {
    const name = newMenuName.trim()
    if (!name) {
      toast.error('Enter a menu name')
      return
    }
    setBusy(true)
    try {
      const menu = await restaurantService.createMenu({
        name,
        is_active: true,
      })
      if (newMenuLocationId) {
        await restaurantService.linkMenuLocation({
          menu: menu.id,
          location: Number(newMenuLocationId),
          is_default: true,
        })
      }
      setNewMenuName('')
      setNewMenuLocationId('')
      await loadMenus()
      setMenuId(menu.id)
      toast.success(`Menu "${menu.name}" created`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create menu')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleActive = async () => {
    if (!selectedMenu) return
    setBusy(true)
    try {
      await restaurantService.updateMenu(selectedMenu.id, {
        is_active: !selectedMenu.is_active,
      })
      await loadMenus()
      toast.success(selectedMenu.is_active ? 'Menu deactivated' : 'Menu activated for POS')
    } catch {
      toast.error('Could not update menu')
    } finally {
      setBusy(false)
    }
  }

  const handleLinkLocation = async (locationId: number) => {
    if (!menuId || linkedLocationIds.includes(locationId)) return
    setBusy(true)
    try {
      await restaurantService.linkMenuLocation({
        menu: menuId,
        location: locationId,
        is_default: linkedLocationIds.length === 0,
      })
      await loadMenuLinks(menuId)
      toast.success('Location linked')
    } catch {
      toast.error('Could not link location')
    } finally {
      setBusy(false)
    }
  }

  const handleAddItem = async (itemNo: string) => {
    if (!menuId) return
    setBusy(true)
    try {
      await restaurantService.createMenuItem({
        item: itemNo,
        menu: menuId,
        is_available: true,
      })
      await loadCatalog(menuId)
      await refreshPreview(menuId)
      setItemSearch('')
      setItemHits([])
      toast.success('Item added to menu')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not add item')
    } finally {
      setBusy(false)
    }
  }

  const handleRemoveItem = async (row: RestaurantMenuItem) => {
    if (!menuId) return
    setBusy(true)
    try {
      await restaurantService.deleteMenuItem(row.id)
      await loadCatalog(menuId)
      await refreshPreview(menuId)
      toast.success('Removed from menu')
    } catch {
      toast.error('Could not remove item')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleAvailable = async (row: RestaurantMenuItem) => {
    if (!menuId) return
    setBusy(true)
    try {
      await restaurantService.updateMenuItem(row.id, {
        is_available: !row.is_available,
      })
      await loadCatalog(menuId)
      await refreshPreview(menuId)
    } catch {
      toast.error('Could not update item')
    } finally {
      setBusy(false)
    }
  }

  const handleOpenMenuItemCard = (row: RestaurantMenuItem) => {
    const card = pages.find((p) => p.Name === 'MenuItemCard')
    if (!card) {
      toast.error('Menu Item card page is not available')
      return
    }
    if (!row.system_id) {
      toast.error('This menu item has no system id — refresh the catalog and try again')
      return
    }
    router.push(getCardRecordPath(card.PageId, row.system_id, card.PageType))
  }

  const handleBuildPosGrid = async () => {
    if (!menuId) return
    setBusy(true)
    try {
      const n = await restaurantService.buildPosHomeFromCatalog(menuId)
      await refreshPreview(menuId)
      toast.success(`POS home grid built with ${n} tiles`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not build POS grid')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-2 rounded-xl border border-strokeColor bg-white px-3 py-2">
        <h1 className="text-base font-semibold text-mainTextColor">Menu Builder</h1>
        <select
          value={menuId ?? ''}
          onChange={(e) => setMenuId(e.target.value ? Number(e.target.value) : null)}
          disabled={menusLoading}
          className="ml-2 rounded-lg border border-strokeColor px-2 py-1.5 text-sm"
        >
          <option value="">Select menu…</option>
          {menus.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} {m.is_active ? '' : '(inactive)'}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => void loadMenus()}
          className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-2 py-1 text-xs hover:bg-softBg"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
        {previewCount != null && menuId ? (
          <span className="ml-auto text-xs text-bodyText">
            {previewCount} POS tile{previewCount === 1 ? '' : 's'}
          </span>
        ) : null}
      </header>

      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        <nav className="flex w-40 shrink-0 flex-col gap-1 rounded-xl border border-strokeColor bg-white p-2">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 rounded-lg px-2 py-2 text-left text-sm ${
                tab === id ? 'bg-s1/10 font-medium text-s1' : 'text-bodyText hover:bg-softBg'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        <section className="min-h-0 min-w-0 flex-1 overflow-auto rounded-xl border border-strokeColor bg-white p-4">
          {!menuId && tab !== 'setup' ? (
            <p className="py-12 text-center text-sm text-bodyText">
              Select or create a menu in the Setup tab first.
            </p>
          ) : tab === 'setup' ? (
            <div className="mx-auto max-w-xl space-y-6">
              <div>
                <h2 className="text-sm font-semibold text-mainTextColor">Create menu</h2>
                <p className="mt-1 text-xs text-bodyText">
                  Menus must be <strong>active</strong> and linked to a <strong>location</strong> to
                  appear on Restaurant POS.
                </p>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <input
                    value={newMenuName}
                    onChange={(e) => setNewMenuName(e.target.value)}
                    placeholder="Menu name (e.g. Lunch)"
                    className="flex-1 rounded-lg border border-strokeColor px-3 py-2 text-sm"
                  />
                  <select
                    value={newMenuLocationId}
                    onChange={(e) =>
                      setNewMenuLocationId(e.target.value ? Number(e.target.value) : '')
                    }
                    className="rounded-lg border border-strokeColor px-2 py-2 text-sm"
                  >
                    <option value="">Location (optional)</option>
                    {locations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {(loc.description || loc.code).trim() || loc.code}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void handleCreateMenu()}
                    className="inline-flex items-center justify-center gap-1 rounded-lg bg-s1 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" />
                    New menu
                  </button>
                </div>
              </div>

              {selectedMenu ? (
                <div className="space-y-4 border-t border-strokeColor pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-semibold">{selectedMenu.name}</h2>
                      <p className="text-xs text-bodyText">Code: {selectedMenu.code}</p>
                    </div>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleToggleActive()}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                        selectedMenu.is_active
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {selectedMenu.is_active ? 'Active on POS' : 'Inactive — enable for POS'}
                    </button>
                  </div>

                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-bodyText">
                      Locations
                    </h3>
                    <p className="mt-1 text-xs text-bodyText">
                      Link at least one inventory location where this menu applies (usually the
                      location whose <strong>code</strong> matches your branch).
                    </p>
                    {locations.length === 0 ? (
                      <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                        No inventory locations found. Create a location in Inventory setup with a
                        code matching your branch (e.g. your branch code), then refresh.
                      </p>
                    ) : (
                    <ul className="mt-2 space-y-1">
                      {locations.map((loc) => {
                        const linked = linkedLocationIds.includes(loc.id)
                        return (
                          <li
                            key={loc.id}
                            className="flex items-center justify-between rounded-lg border border-strokeColor px-3 py-2 text-sm"
                          >
                            <span>{(loc.description || loc.code).trim() || loc.code}</span>
                            {linked ? (
                              <span className="text-xs text-emerald-700">Linked</span>
                            ) : (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void handleLinkLocation(loc.id)}
                                className="text-xs font-medium text-s1 hover:underline"
                              >
                                Link
                              </button>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          ) : tab === 'catalog' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-mainTextColor">Add items to menu</h2>
                <p className="text-xs text-bodyText">
                  Search inventory items and add them to this menu catalog. Only{' '}
                  <strong>available</strong> items show on POS.
                </p>
                <div className="relative mt-2">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-bodyText" />
                  <input
                    value={itemSearch}
                    onChange={(e) => setItemSearch(e.target.value)}
                    placeholder="Search items by name or number…"
                    className="w-full rounded-lg border border-strokeColor py-2 pl-9 pr-3 text-sm"
                  />
                </div>
                {searching ? (
                  <p className="mt-2 text-xs text-bodyText">
                    <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
                    Searching…
                  </p>
                ) : itemHits.length > 0 ? (
                  <ul className="mt-2 max-h-48 overflow-auto rounded-lg border border-strokeColor">
                    {itemHits.map((hit) => (
                      <li
                        key={hit.no}
                        className="flex items-center justify-between border-b border-strokeColor px-3 py-2 text-sm last:border-0"
                      >
                        <span>
                          {hit.item_name}{' '}
                          <span className="text-xs text-bodyText">({hit.no})</span>
                        </span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleAddItem(hit.no)}
                          className="text-xs font-medium text-s1 hover:underline"
                        >
                          Add
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>

              <div>
                <h2 className="text-sm font-semibold text-mainTextColor">
                  Catalog ({catalog.length})
                </h2>
                {catalogLoading ? (
                  <div className="flex h-24 items-center justify-center text-bodyText">
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Loading…
                  </div>
                ) : catalog.length === 0 ? (
                  <p className="py-8 text-center text-sm text-bodyText">
                    No items on this menu yet. Search above to add products.
                  </p>
                ) : (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-strokeColor text-xs text-bodyText">
                          <th className="py-2 pr-2">Item</th>
                          <th className="py-2 pr-2">Price</th>
                          <th className="py-2 pr-2">POS</th>
                          <th className="py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {catalog.map((row) => (
                          <tr key={row.id} className="border-b border-strokeColor/60">
                            <td className="py-2 pr-2">
                              <button
                                type="button"
                                onClick={() => handleOpenMenuItemCard(row)}
                                className="text-left hover:underline"
                                title="Open Menu Item card"
                              >
                                <span className="font-medium text-s1">{row.item_name}</span>
                                <span className="ml-1 text-xs text-bodyText">({row.item_no})</span>
                              </button>
                            </td>
                            <td className="py-2 pr-2">{formatDecimalDisplay(row.unit_price)}</td>
                            <td className="py-2 pr-2">
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void handleToggleAvailable(row)}
                                className={`rounded px-2 py-0.5 text-xs ${
                                  row.is_available
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : 'bg-gray-100 text-gray-600'
                                }`}
                              >
                                {row.is_available ? 'Available' : 'Hidden'}
                              </button>
                            </td>
                            <td className="py-2 text-right">
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void handleRemoveItem(row)}
                                className="text-red-600 hover:text-red-800"
                                aria-label="Remove"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-mainTextColor">POS preview</h2>
                  <p className="mt-1 text-sm text-bodyText">
                    {previewCount != null && previewCount > 0
                      ? `${previewCount} tile(s) on Restaurant POS for this menu.`
                      : 'No POS tiles yet. Add catalog items, then build the home grid.'}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busy || !catalog.length}
                  onClick={() => void handleBuildPosGrid()}
                  className="inline-flex items-center gap-2 rounded-lg bg-s1 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  <LayoutGrid className="h-4 w-4" />
                  {previewCount ? 'Rebuild POS home grid' : 'Build POS home grid from catalog'}
                </button>
              </div>

              {previewStack.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setPreviewStack((s) => s.slice(0, -1))}
                  className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-2 py-1 text-xs font-medium hover:bg-softBg"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Back
                </button>
              ) : (
                <p className="text-xs text-bodyText">
                  Same tile layout as Restaurant POS. Tap a category to drill in. Rebuild replaces
                  the home grid with available catalog items (4 columns).
                </p>
              )}

              {previewLoading ? (
                <div className="flex h-40 items-center justify-center text-bodyText">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Loading preview…
                </div>
              ) : previewEntries.length === 0 ? (
                <p className="rounded-lg border border-dashed border-strokeColor px-4 py-12 text-center text-sm text-bodyText">
                  Nothing to show yet. Build the home grid or ensure catalog items are available.
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {previewEntries.map((entry, idx) =>
                    entry.kind === 'group' ? (
                      <button
                        key={`g-${entry.id}`}
                        type="button"
                        onClick={() => setPreviewStack((s) => [...s, entry.id])}
                        style={posTileStyle(entry.tile_color)}
                        className={`flex min-h-24 flex-col items-center justify-center rounded-xl p-3 text-center font-semibold shadow-sm ${posTileClass(entry.tile_color, idx)}`}
                      >
                        <span className="text-sm leading-tight">{entry.name}</span>
                      </button>
                    ) : (
                      <div
                        key={`i-${entry.id}`}
                        style={posTileStyle(entry.tile_accent_color)}
                        className={`relative flex min-h-24 flex-col items-center justify-center rounded-xl p-2 text-center shadow-sm ${posTileClass(entry.tile_accent_color, idx)}`}
                      >
                        <span className="text-sm font-semibold leading-tight">{entry.item_name}</span>
                        <span className="mt-1 text-xs opacity-90">
                          {formatDecimalDisplay(entry.unit_price)}
                        </span>
                        {entry.pos_out_of_stock ? (
                          <span className="absolute right-1 top-1 rounded bg-black/30 px-1 text-[10px]">
                            Out
                          </span>
                        ) : null}
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
