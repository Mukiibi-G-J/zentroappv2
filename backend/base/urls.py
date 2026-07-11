from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ObjectTypeViewSet, ObjectsViewSet

app_name = "base"

router = DefaultRouter()
router.register(r"object-types", ObjectTypeViewSet)
router.register(r"objects", ObjectsViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
