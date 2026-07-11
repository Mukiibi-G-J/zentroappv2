from django.urls import path
from . import views

app_name = "resources"

urlpatterns = [
    # Resources CRUD
    path("api/resources/", views.list_resources, name="list-resources"),
    path("api/resources/create/", views.create_resource, name="create-resource"),
    path("api/resources/<int:resource_id>/", views.get_resource, name="get-resource"),
    path(
        "api/resources/<int:resource_id>/update/",
        views.update_resource,
        name="update-resource",
    ),
    path(
        "api/resources/<int:resource_id>/delete/",
        views.delete_resource,
        name="delete-resource",
    ),
    # Special endpoints
    path(
        "api/resources/available/",
        views.get_available_resources,
        name="available-resources",
    ),
]


