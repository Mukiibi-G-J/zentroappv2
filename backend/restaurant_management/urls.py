from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .public_menu_views import PublicDigitalMenuView
from .views import (
    FloorViewSet,
    FloorSectionViewSet,
    TableViewSet,
    ReservationViewSet,
    MenuCategoryViewSet,
    MenuItemViewSet,
    RestaurantOrderViewSet,
    RestaurantOrderItemViewSet,
    RestaurantDashboardViewSet,
    MenuViewSet,
    MenuLocationViewSet,
    MenuDisplayGroupViewSet,
    MenuLayoutPageViewSet,
    MenuLayoutTileViewSet,
    RestaurantCheckViewSet,
    ModifierGroupViewSet,
    ModifierOptionViewSet,
    MenuItemModifierGroupViewSet,
    OrderItemModifierViewSet,
    OrderActionLogViewSet,
)

app_name = "restaurant_management"

router = DefaultRouter()
router.register(r"floors", FloorViewSet, basename="floor")
router.register(r"floor-sections", FloorSectionViewSet, basename="floor-section")
router.register(r"tables", TableViewSet, basename="table")
router.register(r"reservations", ReservationViewSet, basename="reservation")
router.register(r"menu-categories", MenuCategoryViewSet, basename="menu-category")
router.register(r"menu-items", MenuItemViewSet, basename="menu-item")
router.register(r"orders", RestaurantOrderViewSet, basename="restaurant-order")
router.register(
    r"order-items", RestaurantOrderItemViewSet, basename="restaurant-order-item"
)
router.register(r"dashboard", RestaurantDashboardViewSet, basename="restaurant-dashboard")
router.register(r"menus", MenuViewSet, basename="restaurant-menu")
router.register(
    r"menu-locations",
    MenuLocationViewSet,
    basename="restaurant-menu-location",
)
router.register(
    r"display-groups", MenuDisplayGroupViewSet, basename="menu-display-group"
)
router.register(r"layout-pages", MenuLayoutPageViewSet, basename="menu-layout-page")
router.register(r"layout-tiles", MenuLayoutTileViewSet, basename="menu-layout-tile")
router.register(r"checks", RestaurantCheckViewSet, basename="restaurant-check")
router.register(r"modifier-groups", ModifierGroupViewSet, basename="modifier-group")
router.register(r"modifier-options", ModifierOptionViewSet, basename="modifier-option")
router.register(
    r"menu-item-modifier-groups",
    MenuItemModifierGroupViewSet,
    basename="menu-item-modifier-group",
)
router.register(
    r"order-item-modifiers", OrderItemModifierViewSet, basename="order-item-modifier"
)
router.register(r"action-logs", OrderActionLogViewSet, basename="order-action-log")

urlpatterns = [
    path(
        "api/restaurant/public-menu/",
        PublicDigitalMenuView.as_view(),
        name="public-digital-menu",
    ),
    path(
        "api/restaurant/public-menu/<slug:slug>/",
        PublicDigitalMenuView.as_view(),
        name="public-digital-menu-slug",
    ),
    path("api/restaurant/", include(router.urls)),
]



