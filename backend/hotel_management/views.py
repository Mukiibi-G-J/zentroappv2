from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from . import models
from . import serializers


class RoomAmenityViewSet(viewsets.ModelViewSet):
    """ViewSet for RoomAmenity model"""

    queryset = models.RoomAmenity.objects.all().order_by("category", "name")
    serializer_class = serializers.RoomAmenitySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "is_active"]
    search_fields = ["no", "code", "name", "category"]
    ordering_fields = ["code", "name", "category", "created_at"]
    ordering = ["category", "name"]
    lookup_field = "system_id"
    lookup_url_kwarg = "system_id"


class RoomTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for RoomType model"""

    queryset = models.RoomType.objects.all().order_by("name")
    serializer_class = serializers.RoomTypeSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["no", "name", "description"]
    ordering_fields = ["name", "base_rate", "created_at"]
    ordering = ["name"]
    lookup_field = "system_id"
    lookup_url_kwarg = "system_id"


class RoomViewSet(viewsets.ModelViewSet):
    """ViewSet for Room model"""

    queryset = (
        models.Room.objects.select_related("room_type")
        .all()
        .order_by("floor", "room_number")
    )
    serializer_class = serializers.RoomSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["room_type", "floor", "status", "is_active"]
    search_fields = ["no", "room_number", "notes"]
    ordering_fields = ["room_number", "floor", "status", "created_at"]
    ordering = ["floor", "room_number"]
    lookup_field = "system_id"
    lookup_url_kwarg = "system_id"

    @action(detail=False, methods=["get"], url_path="availability_calendar")
    def availability_calendar(self, request):
        """Placeholder for availability calendar - returns empty for now"""
        return Response({"calendar": []})

    @action(detail=False, methods=["get"], url_path="available_for_booking")
    def available_for_booking(self, request):
        """Get rooms available for booking in date range"""
        queryset = self.get_queryset().filter(
            status=models.RoomStatus.AVAILABLE, is_active=True
        )
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        serializer = serializers.RoomSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="update_status")
    def update_status(self, request, system_id=None):
        """Update room status"""
        room = self.get_object()
        new_status = request.data.get("status")
        notes = request.data.get("notes")
        if new_status:
            if new_status in dict(models.RoomStatus.choices):
                room.status = new_status
            else:
                return Response(
                    {"error": "Invalid status"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if notes is not None:
            room.notes = notes or room.notes
        room.save()
        serializer = serializers.RoomSerializer(room)
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Hotel dashboard stats (total/occupied/available rooms, occupancy rate)"""
    from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

    JWTAuthentication().authenticate(request)
    total = models.Room.objects.filter(is_active=True).count()
    occupied = models.Room.objects.filter(
        is_active=True, status=models.RoomStatus.OCCUPIED
    ).count()
    available = models.Room.objects.filter(
        is_active=True, status=models.RoomStatus.AVAILABLE
    ).count()
    occupancy_rate = round((occupied / total * 100) if total else 0, 1)
    return Response(
        {
            "total_rooms": total,
            "occupied_rooms": occupied,
            "available_rooms": available,
            "todays_checkins": 0,
            "todays_checkouts": 0,
            "pending_arrivals": 0,
            "occupancy_rate": occupancy_rate,
        }
    )
