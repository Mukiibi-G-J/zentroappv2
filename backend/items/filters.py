import django_filters
from django.db.models import Q
from django_filters import rest_framework as filters
from .models import Item


class ItemFilter(filters.FilterSet):
    # Text-based filters
    item_name = filters.CharFilter(lookup_expr="icontains")
    description = filters.CharFilter(lookup_expr="icontains")
    bar_code_no = filters.CharFilter(lookup_expr="icontains")
    shelf_no = filters.CharFilter(lookup_expr="icontains")
    no = filters.CharFilter(lookup_expr="iexact")  # Added: Filter by item number

    # Dropdown filters
    item_category = filters.CharFilter(
        field_name="item_category__code", lookup_expr="exact"
    )
    unit_of_measure = filters.CharFilter(
        field_name="unit_of_measure__code", lookup_expr="exact"
    )
    tracking_code = filters.CharFilter(
        field_name="tracking_code__code", lookup_expr="exact"
    )
    type = filters.CharFilter(lookup_expr="exact")
    costing_method = filters.CharFilter(lookup_expr="exact")

    # Boolean filter
    blocked = filters.BooleanFilter()

    # Range filters for numeric fields
    unit_price_min = filters.NumberFilter(field_name="unit_price", lookup_expr="gte")
    unit_price_max = filters.NumberFilter(field_name="unit_price", lookup_expr="lte")

    # Date range filters
    created_date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")
    updated_date_from = filters.DateFilter(field_name="updated_at", lookup_expr="gte")
    updated_date_to = filters.DateFilter(field_name="updated_at", lookup_expr="lte")

    # Global search
    search = filters.CharFilter(method="global_search")

    class Meta:
        model = Item
        fields = [
            "item_name",
            "description",
            "bar_code_no",
            "shelf_no",
            "no",  # Added: Allow filtering by item number
            "item_category",
            "unit_of_measure",
            "tracking_code",
            "type",
            "costing_method",
            "blocked",
            "unit_price_min",
            "unit_price_max",
            "created_date_from",
            "created_date_to",
            "updated_date_from",
            "updated_date_to",
            "search",
        ]

    def global_search(self, queryset, name, value):
        """Global search across multiple fields"""
        return queryset.filter(
            Q(item_name__icontains=value)
            | Q(description__icontains=value)
            | Q(bar_code_no__icontains=value)
            | Q(shelf_no__icontains=value)
            | Q(no__icontains=value)
        )
