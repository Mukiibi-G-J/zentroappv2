"""Restaurant quick login: company lookup, PIN-per-user login with per-device rate limiting, staff enrollment."""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils.timezone import now
from django_tenants.utils import get_public_schema_name, get_tenant, schema_context
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from authentication.models import CustomUser, RestaurantStaffDevice
from authentication.restaurant_pin_access import (
    restaurant_pin_is_expired,
    user_can_use_restaurant_pin,
)
from authentication.serializers import AuthTokenViewSerializer
from authentication.restaurant_pin_utils import (
    restaurant_pin_taken_in_tenant,
    validate_restaurant_pin_format,
)
from company.models import Company
from helpers.helpers import send_verification_otp

MAX_PIN_ATTEMPTS = 3


class LoginPinThrottle(AnonRateThrottle):
    scope = "login_pin"


def _pin_login_response_for_user(user, request):
    """Issue JWT pair identical to password login."""
    refresh = AuthTokenViewSerializer.get_token(user)
    user.last_login = now()
    user.save(update_fields=["last_login"])
    payload = {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
    if not user.is_verified:
        tenant_obj = get_tenant(request)
        delivery = send_verification_otp(user, tenant_obj.schema_name)
        if delivery.get("email") and delivery.get("sms"):
            payload["otp_channel"] = "both"
        elif delivery.get("sms"):
            payload["otp_channel"] = "sms"
        else:
            payload["otp_channel"] = "email"

    return Response(payload, status=status.HTTP_200_OK)


def _tenant_required_response():
    return Response(
        {
            "detail": (
                "Tenant is required. Send the X-Tenant header with your "
                "restaurant schema name (from company lookup), or use the company subdomain."
            )
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class RestaurantAppCompanyLookupView(APIView):
    """
    Public: resolve company by name for the restaurant mobile app.
    Returns schema_name and whether the restaurant module is enabled.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        name = (request.data.get("company_name") or "").strip()
        if not name:
            return Response(
                {"detail": "company_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context(get_public_schema_name()):
            qs = Company.objects.filter(name__iexact=name)
            count = qs.count()
            if count == 0:
                return Response(
                    {"detail": "Company not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if count > 1:
                return Response(
                    {
                        "detail": (
                            "Multiple companies match this name. Ask your administrator "
                            "for the exact restaurant name or join code."
                        ),
                        "code": "ambiguous_company_name",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company = qs.first()
            restaurant_enabled = company.has_module("restaurant")
            display_name = company.display_name or company.name
            payload = {
                "schema_name": company.schema_name,
                "name": company.name,
                "display_name": display_name,
                "restaurant_enabled": restaurant_enabled,
            }
        return Response(payload, status=status.HTTP_200_OK)


class RestaurantStaffPinLoginView(APIView):
    """
    PIN login. Requires tenant (subdomain or X-Tenant) and device_id.
    device_id is used for rate-limiting only — PIN is matched against
    any active eligible user in the tenant (PIN-per-user design).
    Body: { pin, device_id }
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginPinThrottle]

    def post(self, request):
        raw_pin = request.data.get("pin")
        device_id = (request.data.get("device_id") or "").strip()

        try:
            pin = validate_restaurant_pin_format(raw_pin)
        except serializers.ValidationError:
            return Response(
                {"detail": "Invalid credentials.", "code": "invalid_pin"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not pin or not device_id:
            return Response(
                {"detail": "Invalid credentials.", "code": "invalid_request"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tenant = getattr(request, "tenant", None)
        if tenant is None or tenant.schema_name == get_public_schema_name():
            return _tenant_required_response()

        # Get or create device record (for rate-limiting — no user binding required)
        device, _ = RestaurantStaffDevice.objects.get_or_create(
            device_id=device_id,
            defaults={"is_revoked": False, "failed_attempts": 0},
        )

        if device.is_revoked:
            return Response(
                {"detail": "This device is no longer authorized.", "code": "device_revoked"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if device.failed_attempts >= MAX_PIN_ATTEMPTS:
            return Response(
                {
                    "detail": "PIN locked. Sign in with email and password to reset.",
                    "code": "pin_locked",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if device.locked_until and device.locked_until > now():
            return Response(
                {
                    "detail": "PIN locked. Sign in with email and password to reset.",
                    "code": "pin_locked",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Find the user by PIN across all eligible active users in this tenant
        candidates = list(
            CustomUser.objects.filter(is_active=True)
            .exclude(terminated=True)
            .exclude(restaurant_pin_hash__isnull=True)
            .exclude(restaurant_pin_hash="")
        )

        matched = None
        for u in candidates:
            if not user_can_use_restaurant_pin(u, tenant):
                continue
            if check_password(pin, u.restaurant_pin_hash):
                if matched is not None:
                    # Two users have the same PIN — treat as invalid (enforce uniqueness)
                    matched = None
                    break
                matched = u

        if matched is None:
            # Increment device failed_attempts for rate limiting
            device.failed_attempts += 1
            update_fields = ["failed_attempts", "updated_at"]
            if device.failed_attempts >= MAX_PIN_ATTEMPTS:
                device.locked_until = now() + timedelta(days=3650)
                update_fields.append("locked_until")
            device.save(update_fields=update_fields)
            return Response(
                {"detail": "Invalid credentials.", "code": "invalid_pin"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if restaurant_pin_is_expired(matched):
            return Response(
                {
                    "detail": "PIN expired. Sign in with email and password to set a new PIN.",
                    "code": "pin_expired",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Success — reset device counter and record last user
        device.failed_attempts = 0
        device.locked_until = None
        device.user = matched
        device.save(update_fields=["failed_attempts", "locked_until", "user", "updated_at"])

        return _pin_login_response_for_user(matched, request)


class RestaurantPinDeviceContextView(APIView):
    """
    Public: last staff member who used this device (for kiosk welcome display).
    Returns empty staff_name if device is not yet associated with any user.
    Does not authenticate; PIN is required to obtain tokens.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginPinThrottle]

    def get(self, request):
        device_id = (request.query_params.get("device_id") or "").strip()
        if not device_id:
            return Response(
                {"detail": "device_id is required.", "code": "invalid_request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = getattr(request, "tenant", None)
        if tenant is None or tenant.schema_name == get_public_schema_name():
            return _tenant_required_response()

        try:
            device = RestaurantStaffDevice.objects.select_related("user").get(
                device_id=device_id
            )
        except RestaurantStaffDevice.DoesNotExist:
            # Device not yet registered — return empty, client shows generic PIN screen
            return Response({"staff_name": ""})

        if device.is_revoked:
            return Response(
                {"detail": "This device is no longer authorized.", "code": "device_revoked"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Show last signed-in user's name (may be None if device not yet used)
        user = device.user
        if not user or not user.is_active or getattr(user, "terminated", False):
            return Response({"staff_name": ""})

        staff_name = (getattr(user, "full_name", None) or "").strip() or (
            getattr(user, "username", None) or ""
        ).strip()
        return Response({"staff_name": staff_name})


class RestaurantPinLoginView(APIView):
    r"""
    Legacy: tenant-scoped PIN without device binding (tries all users with a PIN).
    Prefer POST /api/auth/pin/ with device_id for new clients.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginPinThrottle]

    def post(self, request):
        raw_pin = request.data.get("pin")
        device_id = (request.data.get("device_id") or "").strip()
        if device_id:
            return RestaurantStaffPinLoginView().post(request)

        try:
            pin = validate_restaurant_pin_format(raw_pin)
        except serializers.ValidationError:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not pin:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tenant = getattr(request, "tenant", None)
        if tenant is None or tenant.schema_name == get_public_schema_name():
            return _tenant_required_response()

        candidates = list(
            CustomUser.objects.filter(is_active=True)
            .exclude(terminated=True)
            .exclude(restaurant_pin_hash__isnull=True)
            .exclude(restaurant_pin_hash="")
        )
        matched = None
        for u in candidates:
            if check_password(pin, u.restaurant_pin_hash):
                if matched is not None:
                    return Response(
                        {"detail": "Invalid credentials."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                matched = u

        if matched is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if restaurant_pin_is_expired(matched):
            return Response(
                {
                    "detail": "Restaurant PIN expired. Sign in with email and password to set a new PIN.",
                    "code": "pin_expired",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return _pin_login_response_for_user(matched, request)


class RestaurantStaffEnrollView(APIView):
    """Authenticated: set restaurant PIN and bind this device for quick login."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = get_tenant(request)
        if not user_can_use_restaurant_pin(request.user, tenant):
            return Response(
                {"detail": "You are not eligible for restaurant PIN login."},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw_pin = request.data.get("pin")
        device_id = (request.data.get("device_id") or "").strip()
        if not device_id or len(device_id) > 64:
            return Response(
                {"detail": "device_id is required (max 64 characters)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pin = validate_restaurant_pin_format(raw_pin)
        except serializers.ValidationError as exc:
            msg = getattr(exc, "detail", None)
            if isinstance(msg, list) and msg:
                msg = str(msg[0])
            return Response(
                {"detail": msg or "Invalid PIN."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if restaurant_pin_taken_in_tenant(pin, exclude_user_id=user.id):
            return Response(
                {"detail": "This PIN is already assigned to another active user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.restaurant_pin_hash = make_password(pin)
        user.restaurant_pin_set_at = now()
        user.save(update_fields=["restaurant_pin_hash", "restaurant_pin_set_at"])

        RestaurantStaffDevice.objects.update_or_create(
            device_id=device_id,
            defaults={
                "user": user,
                "is_revoked": False,
                "failed_attempts": 0,
                "locked_until": None,
            },
        )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class RestaurantPinStatusView(APIView):
    """Authenticated: PIN eligibility for current user (onboarding / quick-login UI)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = get_tenant(request)
        eligible = user_can_use_restaurant_pin(request.user, tenant)
        has_pin = bool(request.user.restaurant_pin_hash)
        expired = restaurant_pin_is_expired(request.user) if has_pin else False
        return Response(
            {
                "eligible": eligible,
                "has_pin": has_pin,
                "pin_expired": expired,
            },
            status=status.HTTP_200_OK,
        )
