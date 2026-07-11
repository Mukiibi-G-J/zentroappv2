from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from .models import InventorySetup, ManufacturingSetup


@api_view(["GET"])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_inventory_setup(request):
    setup = InventorySetup.objects.first()
    if not setup:
        return Response({"showAdjustmentHistoryBeforeAfter": True})
    return Response({"showAdjustmentHistoryBeforeAfter": setup.show_adjustment_history_before_after})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def get_manufacturing_setup(request):
    setup = ManufacturingSetup.objects.first()
    if not setup:
        return Response({
            "manufacturingEnabled": False,
            "bomNoSeries": None,
            "productionOrderNoSeries": None,
            "workCenterNoSeries": None,
            "machineCenterNoSeries": None,
            "routingNoSeries": None,
        })
    return Response({
        "manufacturingEnabled": setup.manufacturing_enabled,
        "bomNoSeries": setup.bom_no_series_id,
        "bomNoSeriesCode": (setup.bom_no_series.code if setup.bom_no_series else None),
        "productionOrderNoSeries": setup.production_order_no_series_id,
        "workCenterNoSeries": setup.work_center_no_series_id,
        "machineCenterNoSeries": setup.machine_center_no_series_id,
        "routingNoSeries": setup.routing_no_series_id,
    })


@api_view(["PATCH", "PUT"])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_manufacturing_setup(request):
    setup = ManufacturingSetup.objects.first()
    if not setup:
        return Response(
            {"error": "Manufacturing Setup not found. Run seed_manufacturing_setup first."},
            status=status.HTTP_404_NOT_FOUND,
        )
    manufacturing_enabled = request.data.get("manufacturingEnabled")
    if manufacturing_enabled is not None:
        setup.manufacturing_enabled = bool(manufacturing_enabled)
        setup.save()
    return Response({
        "manufacturingEnabled": setup.manufacturing_enabled,
        "bomNoSeries": setup.bom_no_series_id,
        "bomNoSeriesCode": (setup.bom_no_series.code if setup.bom_no_series else None),
    })
