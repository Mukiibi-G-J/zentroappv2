import api from '@/lib/api'
import type {
  CoversChoice,
  InventoryLocation,
  KitchenOrderItem,
  MenuDisplayGroup,
  MenuLayoutPage,
  MenuLayoutTile,
  MenuLocationLink,
  MenuPosTreeResponse,
  OpenPosPayload,
  RestaurantFloor,
  RestaurantMenu,
  RestaurantMenuItem,
  RestaurantOrder,
  RestaurantTable,
} from '@/types/restaurant'

function extractError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { error?: string; detail?: string } } }).response?.data
    if (data?.detail) return String(data.detail).trim()
    if (data?.error) return data.error
  }
  if (err instanceof Error) return err.message
  return 'Request failed'
}

function unwrapList<T>(data: T[] | { results: T[] }): T[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object' && Array.isArray((data as { results?: T[] }).results)) {
    return (data as { results: T[] }).results
  }
  return []
}

export const restaurantService = {
  async getFloors(): Promise<RestaurantFloor[]> {
    const { data } = await api.get<{ results: RestaurantFloor[] }>('/api/restaurant/floors/')
    return unwrapList(data)
  },

  async getTables(): Promise<RestaurantTable[]> {
    const { data } = await api.get<{ results: RestaurantTable[] }>('/api/restaurant/tables/', {
      params: { page_size: 500 },
    })
    return unwrapList(data)
  },

  async getActiveMenus(locationId?: number): Promise<RestaurantMenu[]> {
    const { data } = await api.get<RestaurantMenu[] | { results: RestaurantMenu[] }>(
      '/api/restaurant/menus/active-for-location/',
      { params: locationId ? { location_id: locationId } : {} },
    )
    return unwrapList(data)
  },

  async getMenus(params?: { is_active?: boolean; search?: string }): Promise<RestaurantMenu[]> {
    const { data } = await api.get<RestaurantMenu[] | { results: RestaurantMenu[] }>(
      '/api/restaurant/menus/',
      { params: { page_size: 200, ...params } },
    )
    return unwrapList(data)
  },

  async createMenu(payload: Partial<RestaurantMenu>): Promise<RestaurantMenu> {
    const { data } = await api.post<RestaurantMenu>('/api/restaurant/menus/', payload)
    return data
  },

  async updateMenu(menuId: number, payload: Partial<RestaurantMenu>): Promise<RestaurantMenu> {
    const { data } = await api.patch<RestaurantMenu>(`/api/restaurant/menus/${menuId}/`, payload)
    return data
  },

  async deleteMenu(menuId: number): Promise<void> {
    await api.delete(`/api/restaurant/menus/${menuId}/`)
  },

  async getLocations(): Promise<InventoryLocation[]> {
    const { data } = await api.get<InventoryLocation[] | { results: InventoryLocation[] }>(
      '/api/locations/',
      { params: { page_size: 500 } },
    )
    return unwrapList(data)
  },

  async getMenuLocations(menuId: number): Promise<MenuLocationLink[]> {
    const { data } = await api.get<MenuLocationLink[] | { results: MenuLocationLink[] }>(
      '/api/restaurant/menu-locations/',
      { params: { menu: menuId, page_size: 100 } },
    )
    return unwrapList(data)
  },

  async linkMenuLocation(payload: {
    menu: number
    location: number
    is_default?: boolean
  }): Promise<MenuLocationLink> {
    const { data } = await api.post<MenuLocationLink>('/api/restaurant/menu-locations/', payload)
    return data
  },

  async getMenuItems(params: { menu?: number; is_available?: boolean }): Promise<RestaurantMenuItem[]> {
    const { data } = await api.get<RestaurantMenuItem[] | { results: RestaurantMenuItem[] }>(
      '/api/restaurant/menu-items/',
      { params: { page_size: 500, ...params } },
    )
    return unwrapList(data)
  },

  async createMenuItem(payload: {
    item: string
    menu: number
    is_available?: boolean
  }): Promise<RestaurantMenuItem> {
    const { data } = await api.post<RestaurantMenuItem>('/api/restaurant/menu-items/', payload)
    return data
  },

  async updateMenuItem(
    id: number,
    payload: Partial<RestaurantMenuItem>,
  ): Promise<RestaurantMenuItem> {
    const { data } = await api.patch<RestaurantMenuItem>(`/api/restaurant/menu-items/${id}/`, payload)
    return data
  },

  async deleteMenuItem(id: number): Promise<void> {
    await api.delete(`/api/restaurant/menu-items/${id}/`)
  },

  async getDisplayGroups(menuId: number): Promise<MenuDisplayGroup[]> {
    const { data } = await api.get<MenuDisplayGroup[] | { results: MenuDisplayGroup[] }>(
      '/api/restaurant/display-groups/',
      { params: { menu: menuId, page_size: 500 } },
    )
    return unwrapList(data)
  },

  async createDisplayGroup(payload: Partial<MenuDisplayGroup>): Promise<MenuDisplayGroup> {
    const { data } = await api.post<MenuDisplayGroup>('/api/restaurant/display-groups/', payload)
    return data
  },

  async getLayoutPages(menuId: number): Promise<MenuLayoutPage[]> {
    const { data } = await api.get<MenuLayoutPage[] | { results: MenuLayoutPage[] }>(
      '/api/restaurant/layout-pages/',
      { params: { menu: menuId, page_size: 20 } },
    )
    return unwrapList(data)
  },

  async createLayoutPage(payload: Partial<MenuLayoutPage>): Promise<MenuLayoutPage> {
    const { data } = await api.post<MenuLayoutPage>('/api/restaurant/layout-pages/', payload)
    return data
  },

  async getLayoutTiles(pageId: number): Promise<MenuLayoutTile[]> {
    const { data } = await api.get<MenuLayoutTile[] | { results: MenuLayoutTile[] }>(
      '/api/restaurant/layout-tiles/',
      // ``layout_page`` — not ``page`` (``page`` is DRF pagination and 404s for id >= 2)
      { params: { layout_page: pageId, page_size: 500 } },
    )
    return unwrapList(data)
  },

  async createLayoutTile(payload: Partial<MenuLayoutTile>): Promise<MenuLayoutTile> {
    const { data } = await api.post<MenuLayoutTile>('/api/restaurant/layout-tiles/', payload)
    return data
  },

  async deleteLayoutTile(tileId: number): Promise<void> {
    await api.delete(`/api/restaurant/layout-tiles/${tileId}/`)
  },

  /** Lay out catalog items on the POS home grid (4 columns). */
  async buildPosHomeFromCatalog(menuId: number): Promise<number> {
    const items = await this.getMenuItems({ menu: menuId, is_available: true })
    if (!items.length) {
      throw new Error('Add available catalog items to this menu first.')
    }
    let pages = await this.getLayoutPages(menuId)
    let page = pages[0]
    if (!page) {
      page = await this.createLayoutPage({
        menu: menuId,
        page_number: 1,
        title: 'Home',
      })
    }
    const existing = await this.getLayoutTiles(page.id)
    await Promise.all(existing.map((t) => this.deleteLayoutTile(t.id)))
    const cols = 4
    for (let i = 0; i < items.length; i++) {
      await this.createLayoutTile({
        page: page.id,
        menu_item: items[i].id,
        row: Math.floor(i / cols) + 1,
        column: (i % cols) + 1,
        display_order: i,
      })
    }
    return items.length
  },

  async getMenuPosTree(menuId: number): Promise<MenuPosTreeResponse> {
    const { data } = await api.get<MenuPosTreeResponse>(`/api/restaurant/menus/${menuId}/pos-tree/`)
    return data
  },

  async openPos(tableId: number): Promise<OpenPosPayload> {
    const { data } = await api.post<OpenPosPayload>(`/api/restaurant/tables/${tableId}/open-pos/`)
    return data
  },

  async openCounterPos(): Promise<OpenPosPayload> {
    const { data } = await api.get<OpenPosPayload>('/api/restaurant/orders/open-counter-pos/')
    return data
  },

  async getOrder(orderId: number, hideFired = false): Promise<RestaurantOrder> {
    const { data } = await api.get<RestaurantOrder>(`/api/restaurant/orders/${orderId}/`, {
      params: hideFired ? { hide_fired: '1' } : {},
    })
    return data
  },

  async createOrder(payload: {
    table?: number
    waiter: number
    order_type: 'dine_in' | 'takeout' | 'delivery'
    covers?: CoversChoice
  }): Promise<RestaurantOrder> {
    const { data } = await api.post<RestaurantOrder>('/api/restaurant/orders/', payload)
    return data
  },

  async updateOrder(
    orderId: number,
    payload: Partial<Pick<RestaurantOrder, 'covers' | 'customer'>>,
  ): Promise<RestaurantOrder> {
    const { data } = await api.patch<RestaurantOrder>(`/api/restaurant/orders/${orderId}/`, payload)
    return data
  },

  async splitCheck(
    orderId: number,
    body: { item_ids: number[]; target_name?: string; source_check_id?: number },
  ): Promise<unknown> {
    const { data } = await api.post(`/api/restaurant/orders/${orderId}/split-check/`, body)
    return data
  },

  async moveOrderItems(
    orderId: number,
    body: { item_ids: number[]; target_check_id: number },
  ): Promise<{ moved_count: number }> {
    const { data } = await api.post<{ moved_count: number }>(
      `/api/restaurant/orders/${orderId}/move-items/`,
      body,
    )
    return data
  },

  async addItemsToOrder(
    orderId: number,
    items: Array<{
      item: string
      quantity: number
      unit_price: number
      seat_no?: number | null
    }>,
  ): Promise<RestaurantOrder> {
    const { data } = await api.post<RestaurantOrder>(`/api/restaurant/orders/${orderId}/add-items/`, {
      order_items: items,
    })
    return data
  },

  async fireOrder(orderId: number): Promise<{
    message: string
    updated_count: number
    kitchen_count?: number
    direct_ready_count?: number
    kitchen_order_ticket?: Record<string, unknown> | null
    bar_order_ticket?: Record<string, unknown> | null
  }> {
    const { data } = await api.post<{
      message: string
      updated_count: number
      kitchen_count?: number
      direct_ready_count?: number
      kitchen_order_ticket?: Record<string, unknown> | null
      bar_order_ticket?: Record<string, unknown> | null
    }>(`/api/restaurant/orders/${orderId}/fire/`, {})
    return data
  },

  async deleteOrCancelOrderItem(itemId: number): Promise<void> {
    await api.post(`/api/restaurant/order-items/${itemId}/delete-or-cancel/`)
  },

  async repeatOrderItem(itemId: number): Promise<void> {
    await api.post(`/api/restaurant/order-items/${itemId}/repeat/`)
  },

  async counterCheckout(
    orderId: number,
    body: {
      payment_method_id: number
      customer_id?: number | null
      amount_received?: number | null
      change_amount?: number | null
    },
  ): Promise<{ message: string; invoice: Record<string, unknown>; receipt_no: string }> {
    try {
      const { data } = await api.post(`/api/restaurant/orders/${orderId}/counter-checkout/`, body)
      return data
    } catch (err) {
      throw new Error(extractError(err))
    }
  },

  async checkoutAndPost(
    orderId: number,
    body: {
      payment_method_id: number
      customer_id?: number | null
      combine_orders?: boolean
      check_id?: number | 'main' | null
      amount_received?: number | null
      change_amount?: number | null
    },
  ): Promise<{
    message: string
    invoice: Record<string, unknown>
    receipt_no: string
    order_completed?: boolean
  }> {
    try {
      const { data } = await api.post(`/api/restaurant/orders/${orderId}/checkout-and-post/`, body)
      return data
    } catch (err) {
      throw new Error(extractError(err))
    }
  },

  async getKitchenItems(): Promise<KitchenOrderItem[]> {
    const { data } = await api.get<KitchenOrderItem[]>(
      '/api/restaurant/order-items/kitchen_items/',
    )
    return Array.isArray(data) ? data : []
  },

  async updateOrderItemStatus(itemId: number, status: string): Promise<void> {
    await api.post(`/api/restaurant/order-items/${itemId}/update_status/`, { status })
  },

  async startPreparingOrderItems(itemIds: number[]): Promise<void> {
    await api.post('/api/restaurant/order-items/start-preparing/', { item_ids: itemIds })
  },
}
