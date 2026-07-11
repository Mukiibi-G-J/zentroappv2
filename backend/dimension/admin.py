from django.contrib import admin

from dimension.models import (
    Dimension,
    DimensionValue,
    DimensionSet,
    DimensionSetEntry,
    DefaultDimension,
)


class DimensionSetEntryInline(admin.TabularInline):
    model = DimensionSetEntry
    extra = 0
    readonly_fields = ("dimension_code", "dimension_value")
    can_delete = False


@admin.register(DimensionSet)
class DimensionSetAdmin(admin.ModelAdmin):
    list_display = ("id", "signature")
    readonly_fields = ("signature",)
    inlines = [DimensionSetEntryInline]
    ordering = ["-id"]


@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code", "description")


@admin.register(DimensionValue)
class DimensionValueAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "dimension_code", "dimension_type")
    list_filter = ("dimension_type", "dimension_code")
    search_fields = ("code", "description")


@admin.register(DefaultDimension)
class DefaultDimensionAdmin(admin.ModelAdmin):
    list_display = (
        "table",
        "no",
        "dimension_code",
        "dimension_value",
        "value_posting",
    )
    list_filter = ("dimension_code", "value_posting", "table")
    search_fields = ("no",)
