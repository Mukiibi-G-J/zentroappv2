from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RoomAmenityViewSet,
    RoomTypeViewSet,
    RoomViewSet,
    dashboard_stats,
)

app_name = "hotel_management"

router = DefaultRouter()
router.register(r"amenities", RoomAmenityViewSet, basename="amenity")
router.register(r"room-types", RoomTypeViewSet, basename="room-type")
router.register(r"rooms", RoomViewSet, basename="room")

urlpatterns = [
    path("dashboard/stats/", dashboard_stats),
    path("", include(router.urls)),
]
