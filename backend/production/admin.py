from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html
from django.contrib import messages
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from .models import (
    ProductionBOM,
    BOMLine,
    ProductionOrder,
    ProductionOrderLine,
    ProductionOrderComponent,
    CapacityUnitOfMeasure,
    WorkCenter,
    MachineCenter,
    CapacityLedgerEntry,
    ShopCalendar,
    ShopCalendarWorkingDays,
    ShopCalendarHoliday,
)
from items.models import Item
from items.models import ItemJournal
from items.enums import EntryType
from postings.models import InventoryPostingSetup, GeneralPostingSetup

from .posting import (
    ProductionOrderPostingError,
    ProductionOrderPostingFromPreviewService,
    build_production_posting_preview,
)


class BOMLineInline(admin.TabularInline):
    """
    Inline admin for BOM Lines within ProductionBOM admin.
    Allows editing BOM lines directly in the BOM admin page.
    """

    model = BOMLine
    extra = 1
    fields = [
        "line_type",
        "item",
        "description",
        "quantity_per",
        "unit_of_measure",
        "scrap_pct",
        "notes",
    ]
    readonly_fields = []

    class Media:
        js = ("admin/js/bom_line_uom_filter.js",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "item":
            # For item lines, show all items
            # For production BOM lines, show only items that have a production BOM
            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        elif db_field.name == "unit_of_measure":
            # Get all UOMs - will be filtered by JavaScript based on selected item
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related("item", "unit_of_measure")


@admin.register(ProductionBOM)
class ProductionBOMAdmin(admin.ModelAdmin):
    """
    Admin interface for Production BOM model.
    Provides list display, filters, search, and inline BOM line editing.
    """

    list_display = [
        "bom_code",
        "name",
        "unit_of_measure",
        "status",
        "total_cost_display",
        "profit_margin_display",
        "line_count",
        "is_active",
    ]

    list_filter = ["status", "is_active", "created_at"]

    search_fields = ["bom_code", "name"]

    readonly_fields = ["bom_code", "created_at", "updated_at", "system_id"]

    inlines = [BOMLineInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "bom_code",
                    "name",
                    "unit_of_measure",
                    "status",
                )
            },
        ),
        ("Additional Information", {"fields": ("notes", "is_active")}),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related("unit_of_measure").prefetch_related("lines")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "unit_of_measure":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def total_cost_display(self, obj):
        """Display total cost with currency formatting"""
        total = obj.calculate_total_cost()
        # Format to string first, then pass to format_html
        total_str = f"{float(total):,.0f}"
        return format_html('<span style="font-weight: bold;">UGX {}</span>', total_str)

    total_cost_display.short_description = "Total Cost"

    def profit_margin_display(self, obj):
        """Display profit margin with color coding"""
        margin = obj.calculate_profit_margin()

        if margin >= 50:
            color = "green"
        elif margin >= 30:
            color = "orange"
        elif margin >= 0:
            color = "blue"
        else:
            color = "red"

        # Format margin to string first, then pass to format_html
        margin_str = f"{margin:.2f}"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>', color, margin_str
        )

    profit_margin_display.short_description = "Profit Margin"

    def line_count(self, obj):
        """Display number of BOM lines"""
        count = obj.lines.count()
        return format_html('<span style="color: #666;">{} lines</span>', count)

    line_count.short_description = "Lines"


@admin.register(BOMLine)
class BOMLineAdmin(admin.ModelAdmin):
    """
    Admin interface for individual BOM Lines.
    Mainly for viewing and debugging; lines are typically edited via ProductionBOM inline.
    """

    list_display = [
        "bom",
        "line_type",
        "item",
        "description",
        "quantity_per",
        "unit_of_measure",
        "scrap_pct",
    ]

    list_filter = ["line_type", "bom__is_active"]

    search_fields = [
        "bom__bom_code",
        "bom__name",
        "item__item_name",
        "description",
    ]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("BOM Information", {"fields": ("bom", "line_type")}),
        (
            "Component Details",
            {
                "fields": (
                    "item",
                    "description",
                    "quantity_per",
                    "unit_of_measure",
                    "scrap_pct",
                    "notes",
                ),
                "description": "Select item (for inventory lines) or resource item (for resource lines)",
            },
        ),
        (
            "System Information",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related("bom", "item")


class ProductionOrderLineInline(admin.TabularInline):
    """Inline admin for Production Order Lines"""

    model = ProductionOrderLine
    extra = 1
    fields = [
        "item",
        "due_date",
        "description",
        "start_date",
        "ending_date",
        "quantity",
        "unit_of_measure_code",
        "finished_quantity",
        "remaining_quantity",
        "unit_cost",
        "cost_amount",
    ]
    readonly_fields = ["remaining_quantity", "cost_amount"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "item":
            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        elif db_field.name == "location_code":
            from items.models import Location

            kwargs["queryset"] = Location.objects.all().order_by("code")
        elif db_field.name == "global_dimension_1":
            from dimension.models import DimensionValue

            kwargs["queryset"] = DimensionValue.objects.all().order_by("code")
        elif db_field.name == "production_bom_no":
            kwargs["queryset"] = ProductionBOM.objects.filter(is_active=True).order_by(
                "bom_code"
            )
        elif db_field.name == "unit_of_measure_code":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "production_order",
            "production_order__item",
            "item",
            "location_code",
            "global_dimension_1",
            "production_bom_no",
            "unit_of_measure_code",
        )


class ProductionOrderItemJournalInline(admin.TabularInline):
    """Inline admin for Production Order Item Journals"""

    from items.models import ItemJournal

    model = ItemJournal
    fk_name = "production_order"
    extra = 0
    fields = [
        "document_no",
        "item",
        "entry_type",
        "journal_template",
        "quantity",
        "unit_cost",
        "location_code",
        "date",
        "status",
    ]
    readonly_fields = [
        "document_no",
        "item",
        "entry_type",
        "journal_template",
        "quantity",
        "unit_cost",
        "location_code",
        "date",
        "status",
    ]
    can_delete = False
    show_change_link = True

    def get_queryset(self, request):
        """Filter to only show ItemJournals with PROD. ORDE template"""
        qs = super().get_queryset(request)
        return qs.filter(journal_template__name="PROD. ORDE").select_related(
            "item", "journal_template", "location_code", "user"
        )

    def has_add_permission(self, request, obj=None):
        """Disable adding journals from inline - they're created by Update Production Details"""
        return False


class ProductionOrderComponentInline(admin.TabularInline):
    """Inline admin for Production Order Components"""

    model = ProductionOrderComponent
    extra = 0
    fields = [
        "status",
        "production_order_line",
        "item",
        "item_name",
        "description",
        "unit_of_measure_code",
        "quantity",
        "expected_quantity",
        "remaining_quantity",
        "quantity_per",
        "unit_cost",
        "cost_amount",
        "location_code",
    ]
    readonly_fields = ["remaining_quantity", "cost_amount", "item_name"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "item":
            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        elif db_field.name == "production_order_line":
            # Filter to only show lines from the current production order
            if hasattr(request, "resolver_match") and request.resolver_match:
                try:
                    obj_id = request.resolver_match.kwargs.get("object_id")
                    if obj_id:
                        from .models import ProductionOrder

                        production_order = ProductionOrder.objects.get(pk=obj_id)
                        kwargs["queryset"] = production_order.lines.all()
                except Exception:
                    pass
        elif db_field.name == "location_code":
            from items.models import Location

            kwargs["queryset"] = Location.objects.all().order_by("code")
        elif db_field.name == "unit_of_measure_code":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "production_order",
            "production_order_line",
            "item",
            "unit_of_measure_code",
            "location_code",
        )


@admin.action(description="Preview Posting")
def preview_posting(modeladmin, request, queryset):
    """
    Show preview of posting for selected production order.
    Requires single selection.
    """
    if queryset.count() != 1:
        messages.error(
            request,
            "Please select a single production order to preview posting.",
        )
        return
    obj = queryset.first()
    return modeladmin.preview_production_posting(
        request, obj, show_finish_button=False
    )


@admin.action(description="Finish Production (Preview then Post)")
def finish_production(modeladmin, request, queryset):
    """
    Show preview first; user confirms from preview page to post.
    Requires single selection and order must be in Released status.
    """
    if queryset.count() != 1:
        messages.error(
            request,
            "Please select a single production order to finish.",
        )
        return

    obj = queryset.first()
    if obj.status != "released":
        messages.error(
            request,
            f"Production order {obj.no} is not in Released status. "
            "Only Released orders can be finished.",
        )
        return HttpResponseRedirect(
            reverse("admin:production_productionorder_changelist")
        )

    return modeladmin.preview_production_posting(
        request, obj, show_finish_button=True
    )


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    """
    Admin interface for Production Order model.
    """

    change_form_template = "admin/production/productionorder/change_form.html"
    actions = [preview_posting, finish_production]

    list_display = [
        "no",
        "name",
        "source_type",
        "item",
        "quantity",
        "status",
        "blocked",
        "last_date_modified",
        "created_at",
    ]

    list_filter = ["source_type", "status", "blocked", "created_at", "updated_at"]

    search_fields = [
        "no",
        "name",
        "description",
        "item__item_name",
        "item__no",
    ]

    readonly_fields = [
        "no",
        "created_at",
        "updated_at",
        "system_id",
        "last_date_modified",
    ]

    inlines = [
        ProductionOrderLineInline,
        ProductionOrderComponentInline,
        ProductionOrderItemJournalInline,
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "no",
                    "name",
                    "description",
                )
            },
        ),
        (
            "Source Information",
            {
                "fields": (
                    "source_type",
                    "item",
                    "quantity",
                )
            },
        ),
        (
            "Status",
            {"fields": ("status", "blocked")},
        ),
        (
            "System Information",
            {
                "fields": (
                    "system_id",
                    "created_at",
                    "updated_at",
                    "last_date_modified",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/finish_production_post/",
                self.admin_site.admin_view(self.finish_production_post),
                name="production_productionorder_finish_production_post",
            ),
        ]
        return custom_urls + urls

    def finish_production_post(self, request, object_id):
        """
        Handle POST from preview page to actually post and finish production.
        Uses preview_data from the form to ensure we post exactly what was shown.
        """
        import json
        from django.shortcuts import get_object_or_404

        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:production_productionorder_changelist")
            )

        production_order = get_object_or_404(ProductionOrder, pk=object_id)
        if production_order.status != "released":
            messages.error(
                request,
                f"Production order {production_order.no} is not in Released status.",
            )
            return HttpResponseRedirect(
                reverse("admin:production_productionorder_changelist")
            )

        preview_data_json = request.POST.get("preview_data")
        if not preview_data_json:
            messages.error(
                request,
                "No posting data received. Please go back and use Preview Posting, "
                "then click Finish Production (Post) from the preview page.",
            )
            return HttpResponseRedirect(
                reverse("admin:production_productionorder_changelist")
            )

        try:
            preview_data = json.loads(preview_data_json)
        except (json.JSONDecodeError, TypeError) as e:
            messages.error(
                request,
                f"Invalid posting data: {str(e)}. Please preview again and try posting.",
            )
            return HttpResponseRedirect(
                reverse("admin:production_productionorder_changelist")
            )

        if preview_data.get("document_no") != production_order.no:
            messages.error(
                request,
                "Posting data does not match this production order. Please preview again.",
            )
            return HttpResponseRedirect(
                reverse("admin:production_productionorder_changelist")
            )

        try:
            with transaction.atomic():
                ProductionOrderPostingFromPreviewService(
                    production_order, request.user, preview_data
                ).post()
                production_order.status = "finished"
                production_order.save(update_fields=["status"])
                production_order.lines.update(status="completed")
                production_order.components.update(status="finished")

            messages.success(
                request,
                f"Successfully finished production order {production_order.no}. Journals posted.",
            )
        except ProductionOrderPostingError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error finishing production: {str(e)}")

        return HttpResponseRedirect(
            reverse("admin:production_productionorder_changelist")
        )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related("item").prefetch_related("lines")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "item":
            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def last_date_modified(self, obj):
        """Display last modified date"""
        return obj.updated_at

    last_date_modified.short_description = "Last Date Modified"

    def response_change(self, request, obj):
        """
        Handle custom actions from the change form.
        """
        if "_update_production_details" in request.POST:
            try:
                with transaction.atomic():
                    result = obj.refresh_production_details(
                        user=request.user, request=request
                    )
                messages = []

                if result.get("production_line_created"):
                    messages.append("Production line created")
                elif result.get("production_line_updated"):
                    messages.append("Production line updated")

                if result.get("components_created", 0) > 0:
                    messages.append(
                        f"{result['components_created']} component(s) created"
                    )
                if result.get("components_updated", 0) > 0:
                    messages.append(
                        f"{result['components_updated']} component(s) updated"
                    )
                if result.get("components_removed", 0) > 0:
                    messages.append(
                        f"{result['components_removed']} component(s) removed"
                    )

                messages.append(
                    f"Total BOM lines processed: {result.get('total_bom_lines', 0)}"
                )

                self.message_user(
                    request,
                    f"Production details updated successfully! {' | '.join(messages)}.",
                    level="SUCCESS",
                )
            except ValueError as e:
                self.message_user(
                    request,
                    f"Error updating production details: {str(e)}",
                    level="ERROR",
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Unexpected error updating production details: {str(e)}",
                    level="ERROR",
                )
            return HttpResponseRedirect(request.path)

        if "_preview_posting" in request.POST:
            show_finish = obj.status == "released"
            return self.preview_production_posting(
                request, obj, show_finish_button=show_finish
            )

        return super().response_change(request, obj)

    def preview_production_posting(self, request, obj, show_finish_button=False):
        """
        Preview posting for all item journals linked to this production order.
        Uses build_production_posting_preview to generate data shown in preview.
        When show_finish_button is True, the same data is passed to post on confirm.
        """
        import json as json_module

        try:
            preview_data, errors = build_production_posting_preview(obj)

            if errors:
                for err in errors:
                    messages.error(request, err)
                return HttpResponseRedirect(request.path)

            if not preview_data:
                messages.error(
                    request,
                    "No posting data could be generated. Please run 'Update Production Details' first.",
                )
                return HttpResponseRedirect(request.path)

            # Add display-only fields for template (location_code as string for ILE)
            for ile in preview_data.get("item_ledger_entries", []):
                ile["location_code"] = None
                if ile.get("location_id"):
                    from items.models import Location
                    loc = Location.objects.filter(pk=ile["location_id"]).first()
                    ile["location_code"] = loc.code if loc else None

            # JSON for hidden form field (post uses this exact data)
            preview_data_json = json_module.dumps(preview_data) if show_finish_button else ""

            context = {
                "title": f"Preview Posting - Production Order {obj.no}",
                "production_order": obj,
                "preview_data": preview_data,
                "preview_data_json": preview_data_json,
                "opts": self.model._meta,
                "show_finish_button": show_finish_button,
            }

            return TemplateResponse(
                request,
                "admin/production/productionorder/preview_posting.html",
                context=context,
            )

        except Exception as e:
            messages.error(
                request,
                f"Error generating preview: {str(e)}",
            )
            return HttpResponseRedirect(request.path)


@admin.register(ProductionOrderLine)
class ProductionOrderLineAdmin(admin.ModelAdmin):
    """
    Admin interface for Production Order Line model.
    """

    list_display = [
        "production_order",
        "status",
        "description",
        "location_code",
        "quantity",
        "finished_quantity",
        "remaining_quantity",
        "unit_cost",
        "cost_amount",
        "start_date",
        "ending_date",
    ]

    list_filter = [
        "status",
        "location_code",
        "production_bom_no",
        "created_at",
        "updated_at",
    ]

    search_fields = [
        "production_order__no",
        "production_order__name",
        "description",
        "production_bom_no__bom_code",
        "production_bom_no__name",
    ]

    readonly_fields = [
        "remaining_quantity",
        "cost_amount",
        "created_at",
        "updated_at",
        "system_id",
    ]

    fieldsets = (
        (
            "Production Order Information",
            {"fields": ("production_order", "status")},
        ),
        (
            "Line Details",
            {
                "fields": (
                    "description",
                    "location_code",
                    "global_dimension_1",
                    "production_bom_no",
                )
            },
        ),
        (
            "Quantity Information",
            {
                "fields": (
                    "quantity",
                    "finished_quantity",
                    "remaining_quantity",
                    "unit_of_measure_code",
                )
            },
        ),
        (
            "Cost Information",
            {"fields": ("unit_cost", "cost_amount")},
        ),
        (
            "Date Information",
            {"fields": ("start_date", "ending_date")},
        ),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "production_order",
            "location_code",
            "global_dimension_1",
            "production_bom_no",
            "unit_of_measure_code",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "production_order":
            kwargs["queryset"] = ProductionOrder.objects.all().order_by("-created_at")
        elif db_field.name == "location_code":
            from items.models import Location

            kwargs["queryset"] = Location.objects.all().order_by("code")
        elif db_field.name == "global_dimension_1":
            from dimension.models import DimensionValue

            kwargs["queryset"] = DimensionValue.objects.all().order_by("code")
        elif db_field.name == "production_bom_no":
            kwargs["queryset"] = ProductionBOM.objects.filter(is_active=True).order_by(
                "bom_code"
            )
        elif db_field.name == "unit_of_measure_code":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def remaining_quantity(self, obj):
        """Display remaining quantity"""
        return obj.remaining_quantity

    remaining_quantity.short_description = "Remaining Quantity"

    def cost_amount(self, obj):
        """Display cost amount"""
        return f"{obj.cost_amount:,.2f}"

    cost_amount.short_description = "Cost Amount"


@admin.register(ProductionOrderComponent)
class ProductionOrderComponentAdmin(admin.ModelAdmin):
    """
    Admin interface for Production Order Component model.
    """

    list_display = [
        "production_order",
        "production_order_line",
        "status",
        "item",
        "item_name",
        "quantity",
        "expected_quantity",
        "remaining_quantity",
        "quantity_per",
        "unit_cost",
        "cost_amount",
        "location_code",
    ]

    list_filter = [
        "status",
        "production_order",
        "location_code",
        "created_at",
        "updated_at",
    ]

    search_fields = [
        "production_order__no",
        "production_order__name",
        "item__item_name",
        "item__no",
        "item_name",
        "description",
    ]

    readonly_fields = [
        "remaining_quantity",
        "cost_amount",
        "item_name",
        "created_at",
        "updated_at",
        "system_id",
    ]

    fieldsets = (
        (
            "Production Order Information",
            {"fields": ("production_order", "production_order_line", "status")},
        ),
        (
            "Component Details",
            {
                "fields": (
                    "item",
                    "item_name",
                    "description",
                    "location_code",
                )
            },
        ),
        (
            "Quantity Information",
            {
                "fields": (
                    "quantity",
                    "expected_quantity",
                    "remaining_quantity",
                    "quantity_per",
                    "unit_of_measure_code",
                )
            },
        ),
        (
            "Cost Information",
            {"fields": ("unit_cost", "cost_amount")},
        ),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "production_order",
            "production_order_line",
            "item",
            "unit_of_measure_code",
            "location_code",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "production_order":
            kwargs["queryset"] = ProductionOrder.objects.all().order_by("-created_at")
        elif db_field.name == "production_order_line":
            kwargs["queryset"] = ProductionOrderLine.objects.all().select_related(
                "production_order"
            )
        elif db_field.name == "item":
            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        elif db_field.name == "location_code":
            from items.models import Location

            kwargs["queryset"] = Location.objects.all().order_by("code")
        elif db_field.name == "unit_of_measure_code":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def remaining_quantity(self, obj):
        """Display remaining quantity"""
        return obj.remaining_quantity

    remaining_quantity.short_description = "Remaining Quantity"

    def cost_amount(self, obj):
        """Display cost amount"""
        return f"{obj.cost_amount:,.2f}"

    cost_amount.short_description = "Cost Amount"


@admin.register(CapacityUnitOfMeasure)
class CapacityUnitOfMeasureAdmin(admin.ModelAdmin):
    """Admin interface for Capacity Unit of Measure model"""

    list_display = ["code", "description", "type", "created_at"]
    list_filter = ["type", "created_at"]
    search_fields = ["code", "description"]
    readonly_fields = ["created_at", "updated_at", "system_id"]
    fields = ["code", "description", "type"]


@admin.register(WorkCenter)
class WorkCenterAdmin(admin.ModelAdmin):
    """Admin interface for Work Center model"""

    list_display = [
        "code",
        "name",
        "general_prod_posting_group",
        "shop_calendar_code",
        "unit_of_measure_code",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "general_prod_posting_group",
        "shop_calendar_code",
        "created_at",
    ]
    search_fields = ["code", "name", "description"]
    readonly_fields = ["code", "created_at", "updated_at", "system_id"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Posting",
            {
                "fields": (
                    "general_prod_posting_group",
                    "unit_cost_calculation",
                    "unit_cost",
                    "direct_unit_cost",
                )
            },
        ),
        (
            "Scheduling",
            {
                "fields": (
                    "shop_calendar_code",
                    "unit_of_measure_code",
                    "capacity",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("created_at", "updated_at", "system_id"),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "shop_calendar_code":
            from production.models import ShopCalendar

            kwargs["queryset"] = ShopCalendar.objects.all().order_by("code")
        elif db_field.name == "unit_of_measure_code":
            from production.models import CapacityUnitOfMeasure

            kwargs["queryset"] = CapacityUnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MachineCenter)
class MachineCenterAdmin(admin.ModelAdmin):
    """Admin interface for Machine Center model"""

    list_display = ["code", "name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["code", "name", "description"]
    readonly_fields = ["created_at", "updated_at", "system_id"]


@admin.register(CapacityLedgerEntry)
class CapacityLedgerEntryAdmin(admin.ModelAdmin):
    """Admin interface for Capacity Ledger Entry model"""

    list_display = [
        "document_no",
        "posting_date",
        "type",
        "no",
        "item_no",
        "order_no",
        "quantity",
        "output_quantity",
        "created_at",
    ]
    list_filter = [
        "type",
        "posting_date",
        "order_type",
        "created_at",
    ]
    search_fields = [
        "document_no",
        "no",
        "description",
        "operation_no",
        "order_no__no",
        "item_no__item_name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "system_id",
        "no",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "document_no",
                    "posting_date",
                    "type",
                    "no",
                    "description",
                    "operation_no",
                )
            },
        ),
        (
            "Capacity Reference",
            {
                "fields": (
                    "work_center",
                    "machine_center",
                    "resource",
                )
            },
        ),
        (
            "Time Tracking",
            {
                "fields": (
                    "quantity",
                    "setup_time",
                    "run_time",
                    "stop_time",
                    "output_quantity",
                    "cap_unit_of_measure_code",
                )
            },
        ),
        (
            "Production Order Linkage",
            {
                "fields": (
                    "item_no",
                    "order_type",
                    "order_no",
                    "order_line_no",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "system_id",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "work_center":
            kwargs["queryset"] = WorkCenter.objects.filter(is_active=True).order_by(
                "code"
            )
        elif db_field.name == "machine_center":
            kwargs["queryset"] = MachineCenter.objects.filter(is_active=True).order_by(
                "code"
            )
        elif db_field.name == "resource":
            from resources.models import Resource

            kwargs["queryset"] = Resource.objects.filter(is_active=True).order_by(
                "code"
            )
        elif db_field.name == "item_no":
            from items.models import Item

            kwargs["queryset"] = Item.objects.filter(blocked=False).order_by(
                "item_name"
            )
        elif db_field.name == "order_no":
            kwargs["queryset"] = ProductionOrder.objects.all().order_by("-created_at")
        elif db_field.name == "order_line_no":
            kwargs["queryset"] = ProductionOrderLine.objects.all().order_by(
                "-created_at"
            )
        elif db_field.name == "cap_unit_of_measure_code":
            from items.models import UnitOfMeasure

            kwargs["queryset"] = UnitOfMeasure.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShopCalendar)
class ShopCalendarAdmin(admin.ModelAdmin):
    """Admin interface for Shop Calendar model"""

    list_display = ["code", "description", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["code", "description"]
    readonly_fields = ["created_at", "updated_at", "system_id"]
    fields = ["code", "description"]


@admin.register(ShopCalendarWorkingDays)
class ShopCalendarWorkingDaysAdmin(admin.ModelAdmin):
    """Admin interface for Shop Calendar Working Days model"""

    list_display = [
        "shop_calendar",
        "day",
        "starting_time",
        "ending_time",
        "work_shift_code",
        "created_at",
    ]
    list_filter = ["shop_calendar", "day", "created_at"]
    search_fields = [
        "shop_calendar__code",
        "shop_calendar__description",
        "day",
        "work_shift_code",
    ]
    readonly_fields = ["created_at", "updated_at", "system_id"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "shop_calendar",
                    "day",
                )
            },
        ),
        (
            "Time Schedule",
            {
                "fields": (
                    "starting_time",
                    "ending_time",
                    "work_shift_code",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("created_at", "updated_at", "system_id"),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "shop_calendar":
            kwargs["queryset"] = ShopCalendar.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShopCalendarHoliday)
class ShopCalendarHolidayAdmin(admin.ModelAdmin):
    """Admin interface for Shop Calendar Holiday model"""

    list_display = [
        "shop_calendar",
        "starting_date_time",
        "ending_time",
        "description",
        "created_at",
    ]
    list_filter = ["shop_calendar", "starting_date_time", "created_at"]
    search_fields = [
        "shop_calendar__code",
        "shop_calendar__description",
        "description",
    ]
    readonly_fields = ["created_at", "updated_at", "system_id"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "shop_calendar",
                    "description",
                )
            },
        ),
        (
            "Holiday Schedule",
            {
                "fields": (
                    "starting_date_time",
                    "ending_time",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("created_at", "updated_at", "system_id"),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "shop_calendar":
            kwargs["queryset"] = ShopCalendar.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
