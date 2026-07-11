from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html

from base.models import Objects
from dimension.models import DefaultDimension, Dimension, DimensionValue
from .models import Resource, ResourceLedgerEntry, ResourceUnitOfMeasure


class ResourceAdminForm(forms.ModelForm):
    """
    Form for Resource with two dimension fields:
    1. Dimension Code - picks from Dimensions table
    2. Dimension Value Code - filtered by selected Dimension Code (from DimensionValue)
    """

    dimension_code = forms.ModelChoiceField(
        queryset=Dimension.objects.all().order_by("code"),
        required=False,
        label="Dimension Code",
        help_text="Select a dimension from the Dimensions table.",
    )
    dimension_value = forms.ModelChoiceField(
        queryset=DimensionValue.objects.none(),
        required=False,
        label="Dimension Value Code",
        help_text="Select a value; options are filtered by the Dimension Code above.",
    )

    class Meta:
        model = Resource
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if instance and instance.pk and instance.code:
            table_obj = Objects.objects.filter(
                object_type="Table", related_model="resources.Resource"
            ).first()
            if table_obj:
                default_dim = (
                    DefaultDimension.objects.filter(
                        table=table_obj, no=instance.code
                    )
                    .select_related("dimension_code", "dimension_value")
                    .first()
                )
                if default_dim:
                    self.fields["dimension_code"].initial = default_dim.dimension_code
                    self.fields["dimension_value"].queryset = (
                        DimensionValue.objects.filter(
                            dimension_code=default_dim.dimension_code
                        ).order_by("code")
                    )
                    self.fields["dimension_value"].initial = default_dim.dimension_value
                    return
        self.fields["dimension_value"].queryset = DimensionValue.objects.none()

    def save(self, commit=True):
        resource = super().save(commit=commit)
        dimension_code = self.cleaned_data.get("dimension_code")
        dimension_value = self.cleaned_data.get("dimension_value")

        table_obj = Objects.objects.filter(
            object_type="Table", related_model="resources.Resource"
        ).first()

        if not table_obj or not resource.code:
            return resource

        if dimension_code and dimension_value:
            if dimension_value.dimension_code_id != dimension_code.code:
                return resource
            DefaultDimension.objects.update_or_create(
                table=table_obj,
                no=resource.code,
                dimension_code=dimension_code,
                defaults={"dimension_value": dimension_value},
            )
        else:
            DefaultDimension.objects.filter(table=table_obj, no=resource.code).delete()

        return resource


class ResourceUnitOfMeasureInline(admin.TabularInline):
    model = ResourceUnitOfMeasure
    extra = 0
    fields = ("unit_of_measure", "quantity_per_unit", "default")
    autocomplete_fields = ["unit_of_measure"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """
    Admin interface for Resource model.
    Provides list display, filters, search, and inline editing capabilities.
    """

    form = ResourceAdminForm
    inlines = [ResourceUnitOfMeasureInline]

    list_display = [
        "code",
        "name",
        "resource_type",
        "direct_unit_cost_display",
        "indirect_cost_pct",
        "unit_cost_display",
        "unit_price_display",
        "profit_margin_display",
        "blocked",
        "is_active",
    ]

    list_filter = ["resource_type", "is_active", "blocked", "base_unit"]

    search_fields = ["code", "name", "description"]

    list_editable = ["is_active", "blocked"]
    autocomplete_fields = ["base_unit"]

    readonly_fields = [
        "code",
        "unit_cost",
        "indirect_cost_amount_display",
        "default_dimensions_table",
        "created_at",
        "updated_at",
        "system_id",
    ]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("code", "name", "resource_type")},
        ),
        (
            "Cost Structure (Business Central Approach)",
            {
                "fields": (
                    "base_unit",
                    "direct_unit_cost",
                    "indirect_cost_pct",
                    "indirect_cost_amount_display",
                    "unit_cost",
                    "unit_price",
                ),
                "description": "Unit Cost is auto-calculated: Direct Unit Cost + (Direct Unit Cost × Indirect Cost %)",
            },
        ),
        (
            "Posting & Status",
            {"fields": ("general_product_posting_group", "is_active", "blocked")},
        ),
        (
            "Dimensions",
            {
                "fields": ("default_dimensions_table", "dimension_code", "dimension_value"),
                "description": (
                    "1. Select Dimension Code (from Dimensions table). "
                    "2. Dimension Value Code is then filtered by that dimension. "
                    "Table above shows current default dimensions."
                ),
            },
        ),
        (
            "Additional Information",
            {"fields": ("description", "photo"), "classes": ("collapse",)},
        ),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def default_dimensions_table(self, obj):
        """
        Display Default Dimensions for this resource in a table with three columns:
        Dimension Code, Dimension Value Code, Dimension Value Name.
        """
        if not obj or not obj.pk or not obj.code:
            return format_html(
                "<p style='color:#666;'>Save the resource first to view default dimensions.</p>"
            )

        table_obj = Objects.objects.filter(
            object_type="Table", related_model="resources.Resource"
        ).first()
        if not table_obj:
            return format_html(
                "<p style='color:#666;'>Resources table not configured. Cannot load default dimensions.</p>"
            )

        rows = (
            DefaultDimension.objects.filter(table=table_obj, no=obj.code)
            .select_related("dimension_code", "dimension_value")
            .order_by("dimension_code__code")
        )

        if not rows:
            return format_html(
                "<p style='color:#666;'>No default dimensions. Select Dimension Code, then Dimension Value Code below.</p>"
            )

        html = (
            '<table style="width:100%; border-collapse:collapse; margin-bottom:1em;">'
            "<thead><tr style='background:#f5f5f5;'>"
            "<th style='padding:8px; border:1px solid #ddd; text-align:left;'>Dimension Code</th>"
            "<th style='padding:8px; border:1px solid #ddd; text-align:left;'>Dimension Value Code</th>"
            "<th style='padding:8px; border:1px solid #ddd; text-align:left;'>Dimension Value Name</th>"
            "</tr></thead><tbody>"
        )
        for row in rows:
            dim_code = row.dimension_code.code if row.dimension_code else "—"
            val_code = row.dimension_value.code if row.dimension_value else "—"
            val_name = (
                row.dimension_value.description if row.dimension_value else "—"
            )
            html += (
                f"<tr>"
                f"<td style='padding:8px; border:1px solid #ddd;'>{dim_code}</td>"
                f"<td style='padding:8px; border:1px solid #ddd;'>{val_code}</td>"
                f"<td style='padding:8px; border:1px solid #ddd;'>{val_name}</td>"
                f"</tr>"
            )
        html += "</tbody></table>"
        return format_html(html)

    default_dimensions_table.short_description = "Default Dimensions"

    def direct_unit_cost_display(self, obj):
        """Display direct unit cost with comma formatting"""
        return f"{obj.direct_unit_cost:,.2f}"

    direct_unit_cost_display.short_description = "Direct Unit Cost"

    def unit_cost_display(self, obj):
        """Display unit cost with comma formatting"""
        return f"{obj.unit_cost:,.2f}"

    unit_cost_display.short_description = "Unit Cost"

    def unit_price_display(self, obj):
        """Display unit price with comma formatting"""
        return f"{obj.unit_price:,.2f}"

    unit_price_display.short_description = "Unit Price"

    def indirect_cost_amount_display(self, obj):
        """Display calculated indirect cost amount with comma formatting"""
        amount = obj.indirect_cost_amount
        amount_str = f"{amount:,.2f}"
        return format_html(
            '<span style="color: #666; font-style: italic;">{}</span>', amount_str
        )

    indirect_cost_amount_display.short_description = "Indirect Cost Amount"

    def profit_margin_display(self, obj):
        """Display profit margin with color coding"""
        margin = obj.profit_margin
        margin_str = f"{margin:.2f}"
        if margin >= 50:
            color = "green"
        elif margin >= 30:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>', color, margin_str
        )

    profit_margin_display.short_description = "Profit Margin"

    def get_queryset(self, request):
        """Optimize queryset with select_related for dimension and posting group"""
        queryset = super().get_queryset(request)
        return queryset.select_related("general_product_posting_group")

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom = [
            path(
                "dimension-values/",
                self.admin_site.admin_view(self.dimension_values_json),
                name="resources_resource_dimension_values",
            ),
        ]
        return custom + urls

    def dimension_values_json(self, request):
        """Return JSON list of dimension values filtered by dimension_code."""
        dimension_code = request.GET.get("dimension_code", "").strip()
        if not dimension_code:
            return JsonResponse({"values": []})
        values = list(
            DimensionValue.objects.filter(dimension_code_id=dimension_code)
            .order_by("code")
            .values("code", "description")
        )
        return JsonResponse({"values": values})

    class Media:
        js = ("admin/js/resource_dimension_filter.js",)


@admin.register(ResourceUnitOfMeasure)
class ResourceUnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ["resource", "unit_of_measure", "quantity_per_unit", "default"]
    list_filter = ["default"]
    search_fields = ["resource__code", "resource__name", "unit_of_measure__code"]
    autocomplete_fields = ["resource", "unit_of_measure"]


@admin.register(ResourceLedgerEntry)
class ResourceLedgerEntryAdmin(admin.ModelAdmin):
    list_display = [
        "document_no",
        "posting_date",
        "resource",
        "entry_type",
        "description",
        "quantity",
        "unit_of_measure",
        "total_cost",
        "total_price",
        "unit_price",
        "source_type",
        "source_no",
        "qty_per_unit_of_measure",
        "quantity_base",
    ]
    list_filter = ["entry_type", "source_type", "posting_date"]
    search_fields = ["document_no", "resource__code", "resource__name", "description", "source_no"]
    readonly_fields = ["created_at", "updated_at", "system_id"]
    autocomplete_fields = ["resource", "unit_of_measure"]
    date_hierarchy = "posting_date"
