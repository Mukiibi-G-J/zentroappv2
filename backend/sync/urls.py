from django.urls import path

from sync import views

app_name = "sync"

urlpatterns = [
    path("api/sync/ping/", views.sync_ping, name="sync-ping"),
    path(
        "api/sync/register-device/",
        views.register_device,
        name="sync-register-device",
    ),
    path("api/sync/bootstrap/", views.sync_bootstrap, name="sync-bootstrap"),
    path("api/sync/pull/items/", views.pull_items, name="sync-pull-items"),
    path(
        "api/sync/pull/customers/",
        views.pull_customers,
        name="sync-pull-customers",
    ),
    path(
        "api/sync/pull/payment-methods/",
        views.pull_payment_methods,
        name="sync-pull-payment-methods",
    ),
    path(
        "api/sync/pull/vendors/",
        views.pull_vendors,
        name="sync-pull-vendors",
    ),
    path("api/sync/changes/", views.sync_changes, name="sync-changes"),
    path("api/sync/push/", views.sync_push, name="sync-push"),
]
