from django.contrib import admin
from django.db.models import Count

from pages.models import Page, PageAction, PageControl, PageControlField


class PageControlInline(admin.TabularInline):
    model = PageControl
    fk_name = "page"
    extra = 0
    fields = (
        "name",
        "caption",
        "control_type",
        "source_table",
        "show_caption",
        "editable",
        "visible",
    )
    show_change_link = True


class PageActionInline(admin.TabularInline):
    model = PageAction
    extra = 0
    fields = (
        "name",
        "caption",
        "visible",
        "requires_confirmation",
        "action_relative_url",
        "ribbon_tab",
    )
    show_change_link = True


class PageControlFieldInline(admin.TabularInline):
    model = PageControlField
    extra = 0
    fk_name = "page"
    fields = (
        "page_control",
        "name",
        "caption",
        "field_type",
        "visible",
        "editable",
        "required",
        "tab_index",
    )
    show_change_link = True
    autocomplete_fields = ("page_control", "lookup_page", "drill_down_page")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("page_control", "lookup_page", "drill_down_page")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = (
        "page_id",
        "name",
        "caption",
        "page_type",
        "source_table",
        "editable",
        "control_count",
        "field_count",
        "action_count",
    )
    list_filter = (
        "page_type",
        "editable",
        "insert_allowed",
        "delete_allowed",
        "modify_allowed",
    )
    search_fields = ("name", "caption", "source_table", "document_type")
    ordering = ("page_id",)
    autocomplete_fields = ("card_page", "header_page")
    inlines = [PageControlInline, PageActionInline, PageControlFieldInline]

    fieldsets = (
        (
            "Page",
            {
                "fields": (
                    "name",
                    "caption",
                    "source_table",
                    "page_type",
                    "title_field",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "editable",
                    "insert_allowed",
                    "delete_allowed",
                    "modify_allowed",
                )
            },
        ),
        (
            "Navigation",
            {
                "fields": (
                    "card_page",
                    "header_page",
                    "context_filter_field",
                    "context_key_field",
                )
            },
        ),
        (
            "Document / List",
            {
                "fields": (
                    "document_type",
                    "list_exclude_field",
                    "list_exclude_values",
                    "list_filter_field",
                    "list_filter_value",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _control_count=Count("page_controls", distinct=True),
            _field_count=Count("fields", distinct=True),
            _action_count=Count("page_actions", distinct=True),
        ).select_related("card_page", "header_page")

    def control_count(self, obj):
        return obj._control_count

    control_count.short_description = "Controls"
    control_count.admin_order_field = "_control_count"

    def field_count(self, obj):
        return obj._field_count

    field_count.short_description = "Fields"
    field_count.admin_order_field = "_field_count"

    def action_count(self, obj):
        return obj._action_count

    action_count.short_description = "Actions"
    action_count.admin_order_field = "_action_count"


class PageControlFieldControlInline(admin.TabularInline):
    model = PageControlField
    extra = 0
    fields = (
        "name",
        "caption",
        "field_type",
        "visible",
        "editable",
        "required",
        "tab_index",
        "primary_key",
    )
    show_change_link = True
    autocomplete_fields = ("page", "lookup_page", "drill_down_page")


@admin.register(PageControl)
class PageControlAdmin(admin.ModelAdmin):
    list_display = (
        "page_control_id",
        "page",
        "name",
        "caption",
        "control_type",
        "source_table",
        "visible",
        "field_count",
    )
    list_filter = ("control_type", "show_caption", "editable", "visible")
    search_fields = ("name", "caption", "source_table", "page__name", "page__caption")
    autocomplete_fields = ("page",)
    inlines = [PageControlFieldControlInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "page",
                    "name",
                    "caption",
                    "control_type",
                    "source_table",
                )
            },
        ),
        (
            "Display",
            {
                "fields": (
                    "show_caption",
                    "editable",
                    "visible",
                )
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_field_count=Count("fields", distinct=True)).select_related(
            "page"
        )

    def field_count(self, obj):
        return obj._field_count

    field_count.short_description = "Fields"
    field_count.admin_order_field = "_field_count"


@admin.register(PageControlField)
class PageControlFieldAdmin(admin.ModelAdmin):
    list_display = (
        "page_control_field_id",
        "page",
        "page_control",
        "name",
        "caption",
        "field_type",
        "visible",
        "editable",
        "required",
        "tab_index",
    )
    list_filter = (
        "field_type",
        "visible",
        "editable",
        "required",
        "primary_key",
        "has_lookup_page",
        "has_drill_down_page",
        "has_table_relation",
        "freeze_column",
    )
    search_fields = (
        "name",
        "caption",
        "page__name",
        "page_control__name",
        "related_table",
        "related_field",
    )
    ordering = ("page", "tab_index", "page_control_field_id")
    autocomplete_fields = ("page", "page_control", "lookup_page", "drill_down_page")

    fieldsets = (
        (
            "Field",
            {
                "fields": (
                    "page",
                    "page_control",
                    "field_id",
                    "name",
                    "caption",
                    "field_type",
                    "tab_index",
                    "tooltip",
                )
            },
        ),
        (
            "Behavior",
            {
                "fields": (
                    "visible",
                    "editable",
                    "primary_key",
                    "required",
                    "freeze_column",
                    "enum_values",
                    "no_series_code",
                )
            },
        ),
        (
            "Lookup",
            {
                "fields": (
                    "has_lookup_page",
                    "lookup_page",
                    "has_drill_down_page",
                    "drill_down_page",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Table Relation",
            {
                "fields": (
                    "has_table_relation",
                    "related_table",
                    "related_field",
                    "related_display_field",
                    "relation_context_field",
                    "relation_context_default",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Conditional Visibility",
            {
                "fields": (
                    "visible_when_field",
                    "visible_when_values",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("page", "page_control", "lookup_page", "drill_down_page")


@admin.register(PageAction)
class PageActionAdmin(admin.ModelAdmin):
    list_display = (
        "action_id",
        "page",
        "name",
        "caption",
        "visible",
        "requires_confirmation",
        "action_relative_url",
        "ribbon_tab",
    )
    list_filter = ("visible", "requires_confirmation", "ribbon_tab")
    search_fields = ("name", "caption", "page__name", "action_relative_url")
    autocomplete_fields = ("page",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "page",
                    "name",
                    "caption",
                    "visible",
                    "tooltip",
                    "image_url",
                )
            },
        ),
        (
            "Action",
            {
                "fields": (
                    "action_relative_url",
                    "ribbon_tab",
                    "requires_confirmation",
                    "confirmation_message",
                )
            },
        ),
        (
            "Conditional Visibility",
            {
                "fields": (
                    "visible_when_field",
                    "visible_when_values",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("page")
