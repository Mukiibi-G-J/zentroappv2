from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from postings.models import (
    GeneralProductPostingGroup,
    GeneralBusinessPostingGroup,
    GeneralPostingSetup,
    VATBusinessPostingGroup,
    VATProductPostingGroup,
    VATPostingSetup,
    InventoryPostingGroup,
    InventoryPostingSetup,
)

from dimension.models import Dimension, DimensionValue

# Import sync utilities
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json


@admin.register(GeneralPostingSetup)
class GeneralPostingSetupAdmin(admin.ModelAdmin):
    list_display = (
        "general_product_posting_group",
        "general_business_posting_group",
        "sales_account",
        "sales_line_discount_account",
        "purchase_account",
        "cogs_account",
        "inventory_adjustment_account",
        "prepayment_account",
    )
    autocomplete_fields = [
        "general_product_posting_group",
        "general_business_posting_group",
        "sales_account",
        "sales_line_discount_account",
        "purchase_account",
        "cogs_account",
        "inventory_adjustment_account",
        "prepayment_account",
    ]
    search_fields = [
        "general_product_posting_group__code",
        "general_business_posting_group__code",
    ]
    actions = [sync_from_json_file, sync_all_models_from_json]


# Admin for GeneralProductPostingGroup
# Admin for GeneralProductPostingGroup
@admin.register(GeneralProductPostingGroup)
class GeneralProductPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "default")
    search_fields = ["code", "description", "default"]
    actions = [sync_from_json_file, sync_all_models_from_json]
    inlines = []


# Admin for GeneralBusinessPostingGroup
@admin.register(GeneralBusinessPostingGroup)
class GeneralBusinessPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "default")
    search_fields = ["code", "description", "default"]
    actions = [sync_from_json_file, sync_all_models_from_json]
    inlines = []


# Admin for VAT posting groups and setup
@admin.register(VATBusinessPostingGroup)
class VATBusinessPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "default")
    search_fields = ["code", "description"]
    inlines = []


@admin.register(VATProductPostingGroup)
class VATProductPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "default")
    search_fields = ["code", "description"]
    inlines = []


@admin.register(VATPostingSetup)
class VATPostingSetupAdmin(admin.ModelAdmin):
    list_display = (
        "vat_business_posting_group",
        "vat_product_posting_group",
        "vat_percent",
        "vat_calculation_type",
        "vat_identifier",
        "sales_vat_account",
        "purchase_vat_account",
    )
    list_filter = ("vat_calculation_type", "vat_percent")
    search_fields = [
        "vat_business_posting_group__code",
        "vat_product_posting_group__code",
        "vat_identifier",
    ]
    autocomplete_fields = [
        "vat_business_posting_group",
        "vat_product_posting_group",
        "sales_vat_account",
        "purchase_vat_account",
    ]


@admin.register(InventoryPostingGroup)
class InventoryPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "default")
    search_fields = ["code", "description", "default"]
    actions = [sync_from_json_file, sync_all_models_from_json]
    inlines = []


@admin.register(InventoryPostingSetup)
class InventoryPostingSetupAdmin(admin.ModelAdmin):
    list_display = ("location", "inventory_posting_group", "inventory_account", "wip_account")
    search_fields = ["inventory_posting_group__code", "inventory_account__code", "wip_account__no"]
    autocomplete_fields = ["inventory_posting_group", "inventory_account", "wip_account"]
    actions = [sync_from_json_file, sync_all_models_from_json]
    inlines = []


