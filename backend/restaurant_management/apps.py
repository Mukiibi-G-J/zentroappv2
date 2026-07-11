from django.apps import AppConfig


class RestaurantManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "restaurant_management"
    verbose_name = "Restaurant Management"

    def ready(self):
        from . import signals  # noqa: F401
