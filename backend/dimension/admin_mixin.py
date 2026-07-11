"""
Mixin for adding DefaultDimension inline formset to Customer, Item, Vendor admin.
"""
from base.models import Objects
from dimension.models import DefaultDimension, Dimension, DimensionValue
from dimension.forms import (
    DefaultDimensionFormSet,
    get_default_dimension_formset,
    save_default_dimension_formset,
)


def _get_dimension_values_by_code():
    """Return {dimension_code_id: [{"id": pk, "code": code}, ...]} for JS filtering."""
    result = {}
    for dim in Dimension.objects.all().order_by("code"):
        values = list(
            DimensionValue.objects.filter(dimension_code=dim)
            .order_by("code")
            .values("id", "code")
        )
        result[str(dim.pk)] = values
    return result


class DefaultDimensionAdminMixin:
    """
    Mixin for ModelAdmin that adds an inline DefaultDimension formset.
    Set on the admin class:
        related_model = "sales.Customer"  # or items.Item, purchases.Vendor
        no_attr = "no"  # attribute name for entity id (default "no")
    """

    related_model = None  # e.g. "sales.Customer"
    no_attr = "no"
    change_form_template = "admin/dimension/change_form_with_default_dimensions.html"

    def _get_table_obj(self):
        if not self.related_model:
            return None
        return Objects.objects.filter(
            object_type="Table", related_model=self.related_model
        ).first()

    def _get_entity_no(self, obj):
        if not obj:
            return None
        return getattr(obj, self.no_attr, None)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            from django.shortcuts import get_object_or_404

            obj = get_object_or_404(self.model, pk=object_id)
            table_obj = self._get_table_obj()
            no = self._get_entity_no(obj)
            if table_obj and no:
                if request.method == "POST":
                    queryset = DefaultDimension.objects.filter(
                        table=table_obj, no=str(no)
                    )
                    formset = DefaultDimensionFormSet(
                        request.POST, request.FILES, queryset=queryset
                    )
                else:
                    formset = get_default_dimension_formset(table_obj, no)
                extra_context["default_dimension_formset"] = formset
                extra_context["default_dimension_table_obj"] = table_obj
                extra_context["default_dimension_no"] = no
                extra_context["show_default_dimensions"] = True
                # Map dimension_code id -> [{id, code}, ...] for JS filtering
                extra_context["dimension_values_by_code"] = _get_dimension_values_by_code()
            else:
                extra_context["show_default_dimensions"] = False
        else:
            extra_context["show_default_dimensions"] = False

        return super().changeform_view(
            request, object_id=object_id, form_url=form_url, extra_context=extra_context
        )

    def response_change(self, request, obj):
        """Save DefaultDimension formset after main object is saved."""
        response = super().response_change(request, obj)
        if request.method == "POST" and hasattr(request, "POST"):
            table_obj = self._get_table_obj()
            no = self._get_entity_no(obj)
            if table_obj and no:
                queryset = DefaultDimension.objects.filter(
                    table=table_obj, no=str(no)
                )
                formset = DefaultDimensionFormSet(
                    request.POST, request.FILES, queryset=queryset
                )
                if save_default_dimension_formset(formset, table_obj, no):
                    self.message_user(
                        request, "Default dimensions saved successfully.", level="SUCCESS"
                    )
                elif formset and not formset.is_valid():
                    self.message_user(
                        request,
                        "Default dimensions could not be saved. Please check for errors.",
                        level="WARNING",
                    )
        return response
