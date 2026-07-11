"""
Forms and formsets for DefaultDimension inline editing in Customer, Item, Vendor admin.
"""
from django import forms
from django.forms import modelformset_factory

from dimension.models import DefaultDimension, Dimension, DimensionValue


class DefaultDimensionInlineForm(forms.ModelForm):
    """Form for a single DefaultDimension row; table and no are set by the formset."""

    class Meta:
        model = DefaultDimension
        fields = ("dimension_code", "dimension_value", "value_posting")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow empty rows in formset (extra forms) without validation errors
        self.fields["dimension_code"].required = False
        self.fields["dimension_value"].required = False
        self.fields["dimension_code"].queryset = Dimension.objects.all().order_by("code")
        # Filter dimension_value by dimension_code so only valid values (e.g. shoe types) show
        dim_code = None
        if self.instance and self.instance.pk and self.instance.dimension_code_id:
            dim_code = self.instance.dimension_code_id
        # Also check POST data when user changed dimension_code or for new rows
        if dim_code is None and self.is_bound and self.data:
            key = self.add_prefix("dimension_code")
            raw = self.data.get(key)
            if raw:
                try:
                    dim_code = int(raw)
                except (TypeError, ValueError):
                    pass
        if dim_code:
            self.fields["dimension_value"].queryset = (
                DimensionValue.objects.filter(dimension_code_id=dim_code).order_by("code")
            )
        else:
            # No dimension code selected: show empty so user picks code first
            self.fields["dimension_value"].queryset = DimensionValue.objects.none()


DefaultDimensionFormSet = modelformset_factory(
    DefaultDimension,
    form=DefaultDimensionInlineForm,
    extra=2,
    can_delete=True,
)


def get_default_dimension_formset(table_obj, no):
    """
    Return a DefaultDimensionFormSet bound to existing data for the given table and no.
    Returns None if table_obj or no is missing.
    """
    if not table_obj or not no:
        return None
    queryset = DefaultDimension.objects.filter(
        table=table_obj, no=str(no)
    ).select_related("dimension_code", "dimension_value")
    return DefaultDimensionFormSet(queryset=queryset)


def save_default_dimension_formset(formset, table_obj, no):
    """
    Save the DefaultDimension formset, setting table and no on each instance.
    Skips empty rows (no dimension_code or dimension_value).
    """
    if not formset.is_valid() or not table_obj or not no:
        return False
    instances = formset.save(commit=False)
    for obj in instances:
        if not obj.dimension_code_id or not obj.dimension_value_id:
            continue  # Skip empty formset rows
        obj.table = table_obj
        obj.no = str(no)
        obj.save()
    for obj in formset.deleted_objects:
        obj.delete()
    return True
