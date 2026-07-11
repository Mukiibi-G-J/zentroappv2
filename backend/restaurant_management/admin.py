from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from . import models


@admin.register(models.FloorSection)
class FloorSectionAdmin(admin.ModelAdmin):
    list_display = ["name", "floor", "display_order", "created_at"]
    list_filter = ["floor"]
    search_fields = ["name"]
    ordering = ["floor", "display_order", "name"]


@admin.register(models.Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ["no", "name", "location", "display_order", "created_at"]
    list_filter = ["created_at", "location"]
    search_fields = ["no", "name", "description"]
    ordering = ["display_order", "name"]
    readonly_fields = ["no", "created_at", "updated_at"]


@admin.register(models.Table)
class TableAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "table_number",
        "floor",
        "capacity",
        "status",
        "shape",
        "created_at",
    ]
    list_filter = ["status", "shape", "floor"]
    search_fields = ["no", "table_number", "notes"]
    ordering = ["floor", "table_number"]
    readonly_fields = ["no", "created_at", "updated_at"]


@admin.register(models.Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "customer",
        "table",
        "reservation_date",
        "party_size",
        "status",
        "waiter",
        "created_at",
    ]
    list_filter = ["status", "reservation_date", "waiter"]
    search_fields = ["no", "customer__name", "special_requests"]
    ordering = ["-reservation_date"]
    readonly_fields = ["no", "created_at", "updated_at"]
    date_hierarchy = "reservation_date"


@admin.register(models.MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ["no", "name", "routes_to_kitchen", "display_order", "is_active", "created_at"]
    list_filter = ["is_active", "routes_to_kitchen", "created_at"]
    search_fields = ["no", "name", "description"]
    ordering = ["display_order", "name"]
    readonly_fields = ["no", "created_at", "updated_at"]
    list_editable = ["is_active", "display_order"]


@admin.register(models.MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = [
        "item",
        "category",
        "menu",
        "display_group",
        "is_available",
        "preparation_time",
        "is_featured",
        "display_order",
    ]
    list_filter = ["category", "is_available", "is_featured"]
    search_fields = ["item__item_name", "description"]
    ordering = ["category", "display_order", "item__item_name"]
    readonly_fields = ["created_at", "updated_at"]


class RestaurantOrderItemInline(admin.TabularInline):
    model = models.RestaurantOrderItem
    extra = 0
    readonly_fields = ["total_price", "created_at"]
    fields = [
        "item",
        "quantity",
        "unit_price",
        "total_price",
        "status",
        "special_instructions",
        "preparation_time",
    ]


@admin.register(models.RestaurantOrder)
class RestaurantOrderAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "table",
        "customer",
        "waiter",
        "global_dimension_1",
        "status",
        "order_type",
        "total_amount",
        "created_at",
    ]
    list_filter = ["status", "order_type", "created_at", "waiter", "global_dimension_1"]
    search_fields = ["no", "table__table_number", "customer__name", "notes"]
    ordering = ["-created_at"]
    readonly_fields = ["no", "total_amount", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    inlines = [RestaurantOrderItemInline]


@admin.register(models.RestaurantOrderItem)
class RestaurantOrderItemAdmin(admin.ModelAdmin):
    list_display = [
        "order",
        "item",
        "quantity",
        "unit_price",
        "total_price",
        "status",
        "seat_no",
        "course",
        "fire_state",
        "preparation_time",
    ]
    list_filter = ["status", "order__status", "fire_state", "course"]
    search_fields = ["order__no", "item__item_name"]
    ordering = ["order", "id"]
    readonly_fields = ["total_price", "created_at", "updated_at"]


@admin.register(models.Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "start_time", "end_time"]
    search_fields = ["name", "code"]


@admin.register(models.MenuLocation)
class MenuLocationAdmin(admin.ModelAdmin):
    list_display = ["menu", "location", "is_default"]


@admin.register(models.MenuDisplayGroup)
class MenuDisplayGroupAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "menu",
        "parent",
        "display_order",
        "is_active",
        "tile_color",
        "icon",
    ]
    list_filter = ["menu", "is_active"]


@admin.register(models.MenuLayoutPage)
class MenuLayoutPageAdmin(admin.ModelAdmin):
    list_display = ["menu", "page_number", "title"]


@admin.register(models.MenuLayoutTile)
class MenuLayoutTileAdmin(admin.ModelAdmin):
    list_display = ["page", "row", "column", "menu_item", "display_group", "display_order"]


@admin.register(models.RestaurantCheck)
class RestaurantCheckAdmin(admin.ModelAdmin):
    list_display = ["order", "name", "status", "total_amount", "is_voided", "is_comped"]


@admin.register(models.ModifierGroup)
class ModifierGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "selection_mode", "required", "is_active"]


@admin.register(models.ModifierOption)
class ModifierOptionAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "group", "price_delta", "is_active"]


@admin.register(models.MenuItemModifierGroup)
class MenuItemModifierGroupAdmin(admin.ModelAdmin):
    list_display = ["menu_item", "modifier_group", "required", "display_order"]


@admin.register(models.OrderItemModifier)
class OrderItemModifierAdmin(admin.ModelAdmin):
    list_display = ["order_item", "modifier_group", "modifier_option", "quantity"]


@admin.register(models.OrderActionLog)
class OrderActionLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "order", "action_type", "actor"]
    list_filter = ["action_type"]

