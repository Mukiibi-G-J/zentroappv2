from django.urls import path
from . import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConfigPackageViewSet, ConfigPackageTableViewSet


app_name = "config_packages"

router = DefaultRouter()
router.register(r"packages", ConfigPackageViewSet)
router.register(r"tables", ConfigPackageTableViewSet)

urlpatterns = [
    path("upload-data/", views.UploadDataView.as_view(), name="upload-data"),
    path("get-model-template/", views.get_model_template, name="get-model-template"),
    path(
        "process-upload-status/<str:process_id>/",
        views.process_upload_status,
        name="process-upload-status",
    ),
    path(
        "config-packages-list/",
        views.ConfigPackageListView.as_view(),
        name="config-packages-list",
    ),
    path(
        "config-packages/save-header/",
        views.save_package_header,
        name="save-package-header",
    ),
    path(
        "config-packages/save-table/",
        views.save_package_table,
        name="save-package-table",
    ),
    path("config-packages/get-tables/", views.get_table_list, name="get-tables"),
    path(
        "config-packages/delete/<str:package_code>/",
        views.delete_package,
        name="delete-package",
    ),
    path(
        "config-packages/<str:package_code>/details/",
        views.get_package_details,
        name="package-details",
    ),
    path(
        "config-packages/export/<str:package_code>/",
        views.export_package,
        name="export-package",
    ),
    path("config-packages/import/", views.import_package, name="import-package"),
    # ignore csrf token on this
    path(
        "api/config/packages/export-tables/", views.export_tables, name="export-tables"
    ),
    path(
        "api/config/packages/import-tables/", views.import_tables, name="import-tables"
    ),
    # path("config-packages/import-tables/", views.import_tables, name="import-tables"),
    path("export-tables/", views.export_tables, name="export_tables"),
    path(
        "get-package-details/<str:package_code>/",
        views.get_package_details,
        name="get_package_details",
    ),
    path(
        "config-packages/validate-import/",
        views.validate_import,
        name="validate-import",
    ),
    path(
        "api/config/packages/check-import-status/<str:task_id>/",
        views.check_import_status,
        name="check-import-status",
    ),
    path(
        "validate-journal-import/",
        views.validate_journal_import,
        name="validate-journal-import",
    ),
    # Field configuration endpoints
    path(
        "api/config/packages/<str:package_code>/tables/<str:table_id>/field-config/",
        views.get_field_config,
        name="get-field-config",
    ),
    path(
        "api/config/packages/<str:package_code>/tables/<str:table_id>/field-config/update/",
        views.update_field_config,
        name="update-field-config",
    ),
    path(
        "api/config/packages/<str:package_code>/tables/<str:table_id>/export-fields/",
        views.get_export_fields,
        name="get-export-fields",
    ),
    path("api/config/", include(router.urls)),
]
