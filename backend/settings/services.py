import hashlib

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from rest_framework import status
from rest_framework.exceptions import ValidationError

from settings.api_errors import error_response
from settings.repositories import MobileAppUserSettingsRepository
from settings.serializers import MobileAppUserSettingsSerializer


class MobileAppUserSettingsService:
    def get_settings(self, user, tenant_schema_name):
        instance, _ = MobileAppUserSettingsRepository.get_or_create_for_user(user)
        return self._build_payload(instance, tenant_schema_name)

    def patch_settings(self, user, tenant_schema_name, data, if_unmodified_since=None):
        instance, _ = MobileAppUserSettingsRepository.get_or_create_for_user(user)

        if if_unmodified_since:
            parsed = parse_datetime(if_unmodified_since)
            if not parsed:
                return None, error_response(
                    code="invalid_if_unmodified_since",
                    message="If-Unmodified-Since must be an ISO datetime.",
                    details={"ifUnmodifiedSince": if_unmodified_since},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if is_naive(parsed):
                parsed = make_aware(parsed)
            if instance.updated_at != parsed:
                return None, error_response(
                    code="settings_conflict",
                    message="Settings were updated by another request.",
                    details={"currentUpdatedAt": instance.updated_at.isoformat()},
                    status_code=status.HTTP_409_CONFLICT,
                )

        serializer = MobileAppUserSettingsSerializer(
            instance=instance,
            data=data,
            partial=True,
        )
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
        except ValidationError as exc:
            return None, error_response(
                code="validation_error",
                message="Invalid settings payload.",
                details=exc.detail,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        instance.refresh_from_db()
        return self._build_payload(instance, tenant_schema_name), None

    def build_cache_headers(self, payload):
        updated_at = payload["updatedAt"]
        etag = hashlib.sha256(updated_at.encode("utf-8")).hexdigest()
        return {
            "Cache-Control": "private, max-age=60",
            "ETag": f"\"{etag}\"",
            "Last-Modified": updated_at,
        }

    def _build_payload(self, instance, tenant_schema_name):
        return {
            "searchMode": instance.search_mode,
            "barcodeScannerEnabled": instance.barcode_scanner_enabled,
            "barcodeBeepEnabled": instance.barcode_beep_enabled,
            "printer": {
                "type": instance.printer_type,
                "deviceName": instance.printer_device_name,
                "macAddress": instance.printer_mac_address,
                "paperWidth": instance.printer_paper_width,
                "copies": instance.printer_copies,
            },
            "tenant": {"currentTenant": tenant_schema_name},
            "updatedAt": instance.updated_at.isoformat(),
        }
