from django.contrib import admin
from .models import UploadTemplates, ConfigPackage, ConfigPackageTable


@admin.register(UploadTemplates)
class UploadTemplatesAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    list_filter = ("name",)


@admin.register(ConfigPackageTable)
class AdminConfigPackageTables(admin.ModelAdmin):
    list_display = ("package_code", "table_id", "table_name", "description")
    list_filter = ("package_code", "table_id")
    search_fields = ("table_name", "description")
    fields = [
        "package_code",
        "table_id",
        "table_name",
        "description",
        "data",
        "field_config",
    ]
    readonly_fields = ["field_config"]


@admin.register(ConfigPackage)
class AdminConfigPackage(admin.ModelAdmin):
    list_display = ("code", "package_name", "status")
    list_filter = ("status",)
    search_fields = ("code", "package_name")
    fields = ["code", "package_name", "status"]
