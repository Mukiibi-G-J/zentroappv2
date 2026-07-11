from django.contrib import admin
from . import models


@admin.register(models.RoomAmenity)
class RoomAmenityAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "category", "icon", "is_active", "created_at"]
    list_filter = ["category", "is_active"]
    search_fields = ["code", "name", "category"]
    ordering = ["category", "name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(models.RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ["no", "name", "base_rate", "max_occupancy", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["no", "name", "description"]
    ordering = ["name"]
    readonly_fields = ["no", "created_at", "updated_at"]


@admin.register(models.Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "room_number",
        "room_type",
        "floor",
        "status",
        "is_active",
        "created_at",
    ]
    list_filter = ["status", "floor", "room_type", "is_active"]
    search_fields = ["no", "room_number", "notes"]
    ordering = ["floor", "room_number"]
    readonly_fields = ["no", "created_at", "updated_at"]
