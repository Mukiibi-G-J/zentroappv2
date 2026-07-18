export interface RestaurantFloor {
  id: number
  no: string
  name: string
  display_order: number
}

export interface RestaurantTable {
  id: number
  no: string
  table_number: string
  floor?: number
  floor_name?: string
  section?: number | null
  section_name?: string
  capacity: number
  status: string
  status_display: string
}

export interface RestaurantMenu {
  id: number
  name: string
  code: string
  is_active: boolean
  start_time?: string | null
  end_time?: string | null
}

export interface RestaurantMenuItem {
  id: number
  system_id?: string
  item: string
  item_no: string
  item_name: string
  unit_price: number
  menu?: number | null
  category?: number | null
  category_name?: string
  is_available: boolean
  display_order: number
  tile_accent_color?: string
}

export interface MenuLocationLink {
  id: number
  menu: number
  location: number
  location_name?: string
  is_default: boolean
}

export interface MenuDisplayGroup {
  id: number
  menu: number
  name: string
  parent?: number | null
  display_order: number
  is_active: boolean
  tile_color: string
  icon: string
}

export interface MenuLayoutPage {
  id: number
  menu: number
  page_number: number
  title: string
}

export interface MenuLayoutTile {
  id: number
  page: number
  menu_item?: number | null
  display_group?: number | null
  row: number
  column: number
  display_order: number
}

export interface InventoryLocation {
  id: number
  code: string
  description?: string
}

export interface PosTreeMenuItem {
  id: number
  item_no: string
  item_name: string
  unit_price: number
  tile_accent_color: string
  kitchen_facing_name: string
  display_order: number
  pos_stock_tracked?: boolean
  pos_available_qty?: number | null
  pos_out_of_stock?: boolean
}

export interface PosTreeGroupNode {
  id: number
  name: string
  tile_color: string
  icon: string
  display_order: number
  children?: PosTreeGroupNode[]
  items?: PosTreeMenuItem[]
}

export interface MenuPosHomeLayoutSlot {
  id: number
  row: number
  column: number
  display_order: number
  accent_color: string
  kind: 'item' | 'group' | 'empty'
  menu_item?: PosTreeMenuItem
  display_group?: {
    id: number
    name: string
    tile_color: string
    icon: string
    display_order: number
  }
}

export interface MenuPosTreeResponse {
  menu: number
  root_groups: PosTreeGroupNode[]
  ungrouped_items: PosTreeMenuItem[]
  home_layout?: MenuPosHomeLayoutSlot[]
}

export interface RestaurantCheckSegment {
  id: number
  name: string
  status: string
  subtotal_amount?: string | number
  total_amount: string | number
  seat_numbers?: number[]
}

export interface RestaurantOrderItem {
  id: number
  order: number
  order_no?: string
  table_number?: string | null
  restaurant_check?: number | null
  item: string
  item_no?: string
  item_name?: string
  quantity: number
  unit_price: number
  total_price: number
  status: string
  status_display: string
  seat_no?: number | null
  fire_state?: string
  fire_state_display?: string
  special_instructions?: string
  waiter_name?: string | null
  preparation_time?: number
  started_at?: string | null
  created_at?: string
}

export type KitchenOrderItem = RestaurantOrderItem

export interface RestaurantOrder {
  id: number
  no: string
  table: number
  table_number?: string
  waiter: number
  waiter_name?: string
  status: string
  status_display: string
  order_type: string
  order_type_display: string
  covers?: number | null
  total_amount: number
  sales_invoice?: number | null
  customer?: number | null
  customer_name?: string | null
  order_items?: RestaurantOrderItem[]
  active_checks?: RestaurantCheckSegment[]
}

export interface OpenPosPayload {
  table: RestaurantTable | null
  active_orders: RestaurantOrder[]
  active_checks_count: number
  unsent_items_count: number
  fired_items_count: number
}

export type CoversChoice = number | null

export type RestaurantPosTab = 'tables' | 'quick-sale' | 'menu'
