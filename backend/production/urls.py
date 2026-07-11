from django.urls import path
from . import views

app_name = "production"

urlpatterns = [
    # Production BOM CRUD
    path("api/production/boms/", views.list_boms, name="list-boms"),
    path("api/production/boms/create/", views.create_bom, name="create-bom"),
    path("api/production/boms/<int:bom_id>/", views.get_bom_detail, name="get-bom"),
    path(
        "api/production/boms/<int:bom_id>/update/",
        views.update_bom,
        name="update-bom",
    ),
    path(
        "api/production/boms/<int:bom_id>/delete/",
        views.delete_bom,
        name="delete-bom",
    ),
    # Cost analysis
    path(
        "api/production/boms/<int:bom_id>/cost-analysis/",
        views.get_cost_analysis,
        name="cost-analysis",
    ),
    # BOM Lines bulk update (for inline editing)
    path(
        "api/production/boms/<int:bom_id>/update_lines/",
        views.update_lines,
        name="update-bom-lines",
    ),
    # BOM Lines
    path(
        "api/production/boms/<int:bom_id>/lines/create/",
        views.create_bom_line,
        name="create-bom-line",
    ),
    path(
        "api/production/bom-lines/<int:line_id>/update/",
        views.update_bom_line,
        name="update-bom-line",
    ),
    path(
        "api/production/bom-lines/<int:line_id>/delete/",
        views.delete_bom_line,
        name="delete-bom-line",
    ),
    # Item Unit of Measures (for BOM line dropdown filtering)
    path(
        "api/production/items/<str:item_no>/unit-of-measures/",
        views.get_item_unit_of_measures,
        name="item-unit-of-measures",
    ),
    # Items with BOM (for production order source dropdown)
    path(
        "api/production/items-with-bom/",
        views.list_items_with_bom,
        name="list-items-with-bom",
    ),
    # Production Orders (Make Production)
    path(
        "api/production/orders/",
        views.list_production_orders,
        name="list-production-orders",
    ),
    path(
        "api/production/orders/create/",
        views.create_production_order,
        name="create-production-order",
    ),
    path(
        "api/production/orders/upsert/",
        views.upsert_production_order,
        name="upsert-production-order",
    ),
    path(
        "api/production/orders/<int:order_id>/",
        views.get_production_order_detail,
        name="get-production-order",
    ),
    path(
        "api/production/orders/<int:order_id>/update/",
        views.update_production_order,
        name="update-production-order",
    ),
    path(
        "api/production/orders/<int:order_id>/refresh/",
        views.refresh_production_order,
        name="refresh-production-order",
    ),
    path(
        "api/production/orders/<int:order_id>/finish/",
        views.finish_production_order,
        name="finish-production-order",
    ),
    path(
        "api/production/orders/<int:order_id>/update_components/",
        views.update_production_order_components,
        name="update-production-order-components",
    ),
    path(
        "api/production/orders/<int:order_id>/update_lines/",
        views.update_production_order_lines,
        name="update-production-order-lines",
    ),
    path(
        "api/production/orders/<int:order_id>/delete/",
        views.delete_production_order,
        name="delete-production-order",
    ),
]
