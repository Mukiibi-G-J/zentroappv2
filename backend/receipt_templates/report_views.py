"""Receipt report API (BC-style numeric report ids)."""

from __future__ import annotations

import logging

from django_tenants.utils import get_tenant
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from receipt_templates.report_registry import get_report_definition, list_report_definitions
from receipt_templates.services.payloads import build_report_payload
from receipt_templates.services.resolution import resolve_receipt_template, template_to_dict

logger = logging.getLogger(__name__)


def _company_branding(request) -> dict:
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
    return branding


class ReceiptReportViewSet(viewsets.ViewSet):
    """
    Run thermal receipt reports by numeric id (Business Central style).

    POST /api/receipt-reports/{report_id}/run/
    Body examples:
      - 50000 Sales: { "invoice_system_id": "..." }
      - 50001 KOT:   { "order_id": 12, "item_ids": [1,2] }  # item_ids optional
      - 50002 Bar:   { "order_id": 12, "item_ids": [3] }
      - 50003 Guest: { "order_id": 12 }
    """

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response({"reports": list_report_definitions()})

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, pk=None):
        definition = get_report_definition(pk)
        if not definition:
            return Response(
                {"error": f"Unknown receipt report id: {pk}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        device_type = request.data.get("device_type", "web")
        printer_type = request.data.get("printer_type", "browser")
        process = request.data.get("process") or definition.process
        branch_id = request.data.get("branch_id")
        branch_pk = int(branch_id) if branch_id and str(branch_id).isdigit() else None

        try:
            payload = build_report_payload(int(pk), request, request.data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("receipt report payload failed report_id=%s", pk)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        template = resolve_receipt_template(
            receipt_type=definition.receipt_type,
            device_type=device_type,
            printer_type=printer_type,
            process=process,
            branch_id=branch_pk,
        )
        if not template:
            return Response(
                {"error": "No receipt template configured for this report."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "reportId": definition.report_id,
                "reportName": definition.name,
                "caption": definition.caption,
                "payload": payload,
                "template": template_to_dict(template),
                "branding": _company_branding(request),
            }
        )
