import logging

from django_tenants.utils import get_tenant
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from receipt_templates.models import ReceiptTemplate, ReceiptTemplateAssignment
from receipt_templates.serializers import (
    ReceiptTemplateAssignmentSerializer,
    ReceiptTemplateSerializer,
)
from receipt_templates.services.resolution import resolve_receipt_template, template_to_dict

logger = logging.getLogger(__name__)


class ReceiptTemplateViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ReceiptTemplateSerializer
    queryset = ReceiptTemplate.objects.all().order_by("receipt_type", "name")

    def get_queryset(self):
        qs = super().get_queryset()
        receipt_type = self.request.query_params.get("receipt_type")
        if receipt_type:
            qs = qs.filter(receipt_type=receipt_type)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response(
                {"error": "System templates cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request):
        receipt_type = request.query_params.get("receipt_type", "sale")
        device_type = request.query_params.get("device_type", "any")
        printer_type = request.query_params.get("printer_type", "any")
        process = request.query_params.get("process", "any")
        branch_id = request.query_params.get("branch_id")
        branch_pk = int(branch_id) if branch_id and str(branch_id).isdigit() else None

        template = resolve_receipt_template(
            receipt_type=receipt_type,
            device_type=device_type,
            printer_type=printer_type,
            process=process,
            branch_id=branch_pk,
        )
        if not template:
            return Response(
                {"error": "No receipt template found for this context."},
                status=status.HTTP_404_NOT_FOUND,
            )

        company = get_tenant(request)
        branding = {
            "name": getattr(company, "name", "") or "",
            "displayName": getattr(company, "display_name", None)
            or getattr(company, "name", "")
            or "",
            "logo": None,
            "address": getattr(company, "address", "") or "",
            "phone": getattr(company, "phone", "") or "",
            "email": getattr(company, "email", "") or "",
            "tin": getattr(company, "tin", "") or "",
        }
        if getattr(company, "logo", None):
            try:
                branding["logo"] = request.build_absolute_uri(company.logo.url)
            except Exception:
                branding["logo"] = None

        return Response(
            {
                "template": template_to_dict(template),
                "branding": branding,
            }
        )


class ReceiptTemplateAssignmentViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ReceiptTemplateAssignmentSerializer
    queryset = ReceiptTemplateAssignment.objects.select_related("template").all()

    def get_queryset(self):
        qs = super().get_queryset()
        receipt_type = self.request.query_params.get("receipt_type")
        if receipt_type:
            qs = qs.filter(template__receipt_type=receipt_type)
        return qs

