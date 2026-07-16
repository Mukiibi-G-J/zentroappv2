from datetime import timedelta

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AppVersion


def _default_landing_url() -> str:
    landing_url = getattr(settings, "APP_LANDING_PAGE_URL", "").strip()
    if landing_url:
        return landing_url
    return "https://zentroapp.app/landing"


def _build_candidate_keys(object_key: str) -> list[str]:
    key = (object_key or "").strip().lstrip("/")
    if not key:
        return []

    candidates = [key]
    if not key.startswith("app_versions/"):
        candidates.append(f"app_versions/{key}")
    if not key.startswith("app_versions/app_versions/"):
        candidates.append(f"app_versions/app_versions/{key}")

    # Keep order, remove duplicates.
    return list(dict.fromkeys(candidates))


def _pick_existing_s3_key(s3_client, object_key: str) -> str:
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    candidates = _build_candidate_keys(object_key)

    for key in candidates:
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return key
        except ClientError:
            continue

    # Fallback to original key when object metadata cannot be validated.
    return object_key


def _get_presigned_s3_url(object_key: str, expires_in: int = 3600) -> str:
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
    )
    resolved_key = _pick_existing_s3_key(s3_client, object_key)
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": resolved_key,
        },
        ExpiresIn=expires_in,
    )


def _resolve_download_url(request, version: AppVersion | None) -> str:
    if version is None:
        return _default_landing_url()

    if version.apk_file:
        # Use a pre-signed URL so private S3 objects are downloadable.
        try:
            return _get_presigned_s3_url(version.apk_file.name)
        except Exception:
            # Fallback to storage-provided URL if signing fails.
            return version.apk_file.url

    if version.download_url.strip():
        return version.download_url.strip()

    return _default_landing_url()


class AppVersionCheckView(APIView):
    """
    Public endpoint. App calls this on launch to check for updates.
    GET /api/app/version-check/?platform=android
    """

    permission_classes = [AllowAny]

    def get(self, request):
        platform = (request.query_params.get("platform") or "android").strip().lower()

        # Get the latest active version for this platform (or 'all').
        qs = AppVersion.objects.filter(
            is_active=True,
            platform__in=[platform, "all"],
        ).order_by("-build_number")

        version = qs.first()
        if version is None:
            # No version configured: let the app through.
            return Response({"status": "ok"})

        download_url = _resolve_download_url(request, version)

        grace_period_ends_at = version.released_at + timedelta(
            days=version.grace_period_days,
        )

        return Response(
            {
                "latest_build": version.build_number,
                "latest_version": version.version_name,
                "min_required_build": version.min_required_build,
                "grace_period_ends_at": grace_period_ends_at.isoformat(),
                "download_url": download_url,
                "release_notes": version.release_notes,
            },
        )


class DownloadLatestAndroidView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        version = (
            AppVersion.objects.filter(is_active=True, platform__in=["android", "all"])
            .order_by("-build_number")
            .first()
        )
        download_url = _resolve_download_url(request, version)
        return redirect(download_url)


class DownloadLatestWindowsView(APIView):
    """Public redirect to the latest active Windows desktop installer."""

    permission_classes = [AllowAny]

    def get(self, request):
        version = (
            AppVersion.objects.filter(is_active=True, platform="windows")
            .order_by("-build_number")
            .first()
        )
        download_url = _resolve_download_url(request, version)
        return redirect(download_url)
