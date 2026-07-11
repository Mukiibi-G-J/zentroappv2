from django.apps import AppConfig


class PermissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "permissions"
    verbose_name = "Permission Management System"

    def ready(self):
        """Initialize the permissions app when Django starts"""
        pass

