from django.urls import path
from . import views

app_name = "setup"

urlpatterns = [
    path("api/setup/inventory/", views.get_inventory_setup, name="get-inventory-setup"),
    path("api/setup/manufacturing/", views.get_manufacturing_setup, name="get-manufacturing-setup"),
    path("api/setup/manufacturing/update/", views.update_manufacturing_setup, name="update-manufacturing-setup"),
]
