from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import (
    ItemCategoryViewSet,
    UnitOfMeasureViewSet,
    ItemTrackingCodeViewSet,
    ItemUnitOfMeasureViewSet,
    ItemJournalViewSet,
    ItemAttributeViewSet,
    ItemAttributeValueViewSet,
    ItemAttributeEntryViewSet,
    LocationViewSet,
    ItemVariantOptionViewSet,
    ItemVariantOptionValueViewSet,
    ItemVariantViewSet,
)

app_name = "items"

router = DefaultRouter()
router.register(r"items", views.ItemsModalViewSet, basename="items-viewset")
router.register(r"item-ledger", views.ItemLedgerViewSet, basename="item-ledger")
router.register(
    r"tracking-specifications",
    views.TrackingSpecificationViewSet,
    basename="tracking-specifications-viewset",
)
router.register(r"categories", ItemCategoryViewSet)
router.register(r"units-of-measure", UnitOfMeasureViewSet)
router.register(r"item-tracking-codes", ItemTrackingCodeViewSet)
router.register(r"item-units-of-measure", ItemUnitOfMeasureViewSet)
router.register(
    r"item-journals", views.ItemJournalViewSet, basename="item-journal-viewset"
)
router.register(r"item-images", views.ItemImagesViewSet, basename="item-images")
router.register(r"item-attributes", ItemAttributeViewSet, basename="item-attributes")
router.register(
    r"item-attribute-values",
    ItemAttributeValueViewSet,
    basename="item-attribute-values",
)
router.register(
    r"item-attribute-entries",
    ItemAttributeEntryViewSet,
    basename="item-attribute-entries",
)
router.register(r"locations", LocationViewSet, basename="locations")
router.register(r"variant-options", ItemVariantOptionViewSet, basename="variant-options")
router.register(r"variant-option-values", ItemVariantOptionValueViewSet, basename="variant-option-values")
router.register(r"variants", ItemVariantViewSet, basename="item-variants")

# ---------------- Web endpoints ---------------- #
urlpatterns = [
    path(
        "api/item-journal/post",
        views.PostItemJournalView.as_view(),
        name="post-item-journal",
    ),
    path(
        "api/item-journal/post-async",
        views.PostItemJournalAsyncView.as_view(),
        name="post-item-journal-async",
    ),
    path("items-list/", views.ItemListView.as_view(), name="items-list"),
    path("item-new/", views.ItemCreateView.as_view(), name="new-item"),
    path(
        "items/<int:pk>/ledger-entries/",
        views.ItemLedgerEntriesView.as_view(),
        name="item-ledger-entries",
    ),
    path("item-edit/<int:pk>/", views.ItemUpdateView.as_view(), name="edit-item"),
    path("item-delete/<int:pk>/", views.ItemDeleteView.as_view(), name="delete-item"),
    path(
        "item-delete-image/<int:pk>/",
        views.ItemDeleteImageView.as_view(),
        name="delete-image",
    ),
    path("item-upload", views.ExcelUpload.as_view(), name="item-upload"),
    path("item-journal/", views.ItemJournalView.as_view(), name="item-journal"),
    path("post-journal", views.PostJournalView.as_view(), name="post-journal"),
]


# ---------------- API endpoints ---------------- #
urlpatterns += [
    # path("api/items/filter/", views.ItemsFilter.as_view(), name="filter-items"),
    # path("api/items/", views.ItemListApiView.as_view(), name="items"),
    # path(
    #     "api/items/item-update/<int:pk>/",
    #     views.ItemUpdateApiView.as_view(),
    #     name="item-update",
    # ),
    path("api/", include(router.urls)),
]


# ---------------- HTMX endpoints ---------------- #
urlpatterns += [
    path("search-items", views.search_items, name="search-items"),
    path("item-unit-of-measure/", views.unit_of_measure, name="unit-of-measure"),
    path(
        "refresh-unit-options/", views.refresh_unit_options, name="refresh-unit-options"
    ),
]


# ---------------- Admin endpoints ---------------- #
urlpatterns += [
    path(
        "admin/api/item/<int:item_id>/cost/", views.get_item_cost, name="get-item-cost"
    ),
]
