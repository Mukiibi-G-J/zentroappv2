from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import only the views that exist
try:
    from .views import PermissionSetViewSet
except ImportError:
    PermissionSetViewSet = None

router = DefaultRouter()
if PermissionSetViewSet:
    router.register(r"permission-sets", PermissionSetViewSet, basename="permissionset")

urlpatterns = [
    # Router URLs
    path("", include(router.urls)),
]
