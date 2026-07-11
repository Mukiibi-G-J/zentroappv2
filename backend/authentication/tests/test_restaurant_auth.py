import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from authentication.models import RestaurantStaffDevice
from authentication.restaurant_auth import (
    RestaurantAppCompanyLookupView,
    RestaurantPinLoginView,
)
from authentication.restaurant_auth import LoginPinThrottle
from authentication.restaurant_pin_utils import validate_restaurant_pin_format
from authentication.user_management_serializers import UserDetailSerializer
from rest_framework.serializers import ValidationError as DRFValidationError


class RestaurantPinFormatTests(SimpleTestCase):
    def test_valid_pins(self):
        self.assertEqual(validate_restaurant_pin_format("1234"), "1234")
        self.assertEqual(validate_restaurant_pin_format(" 123456 "), "123456")

    def test_clear_empty(self):
        self.assertEqual(validate_restaurant_pin_format(""), "")
        self.assertEqual(validate_restaurant_pin_format(None), "")

    def test_invalid_non_digit(self):
        with self.assertRaises(DRFValidationError):
            validate_restaurant_pin_format("12ab")

    def test_invalid_length(self):
        with self.assertRaises(DRFValidationError):
            validate_restaurant_pin_format("123")
        with self.assertRaises(DRFValidationError):
            validate_restaurant_pin_format("1234567")


class RestaurantAppCompanyLookupViewTests(SimpleTestCase):
    def test_requires_company_name(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/restaurant-app/company-lookup/",
            {},
            format="json",
        )
        response = RestaurantAppCompanyLookupView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.restaurant_auth.schema_context")
    @patch("authentication.restaurant_auth.Company")
    def test_lookup_success(self, mock_company, mock_schema_context):
        @contextmanager
        def ctx(*args, **kwargs):
            yield

        mock_schema_context.side_effect = ctx

        company = MagicMock()
        company.schema_name = "demo_schema"
        company.name = "Demo Cafe"
        company.display_name = None
        company.has_module.return_value = True

        qs = MagicMock()
        qs.count.return_value = 1
        qs.first.return_value = company
        mock_company.objects.filter.return_value = qs

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/restaurant-app/company-lookup/",
            {"company_name": "demo cafe"},
            format="json",
        )
        response = RestaurantAppCompanyLookupView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body["schema_name"], "demo_schema")
        self.assertTrue(body["restaurant_enabled"])

    @patch("authentication.restaurant_auth.schema_context")
    @patch("authentication.restaurant_auth.Company")
    def test_lookup_ambiguous(self, mock_company, mock_schema_context):
        @contextmanager
        def ctx(*args, **kwargs):
            yield

        mock_schema_context.side_effect = ctx

        qs = MagicMock()
        qs.count.return_value = 2
        mock_company.objects.filter.return_value = qs

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/restaurant-app/company-lookup/",
            {"company_name": "dup"},
            format="json",
        )
        response = RestaurantAppCompanyLookupView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDetailRestaurantPinValidationTests(SimpleTestCase):
    @patch(
        "authentication.user_management_serializers.restaurant_pin_taken_in_tenant",
        return_value=True,
    )
    def test_validate_rejects_duplicate(self, _mock_taken):
        ser = UserDetailSerializer()
        ser.instance = MagicMock(pk=99)
        with self.assertRaises(DRFValidationError):
            ser.validate_restaurant_pin("1234")


class LoginPinThrottleConfigTests(SimpleTestCase):
    def test_throttle_scope(self):
        self.assertEqual(LoginPinThrottle.scope, "login_pin")


class RestaurantPinLoginViewUnitTests(SimpleTestCase):
    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    def test_missing_tenant_header(self, _mock_pub, _mock_throttle):
        factory = APIRequestFactory()
        request = factory.post("/api/auth/login-pin/", {"pin": "1234"}, format="json")
        request.tenant = MagicMock(schema_name="public")
        response = RestaurantPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.CustomUser.objects.filter")
    def test_wrong_pin_no_users(self, mock_filter, _mock_pub, _mock_throttle):
        chain_end = MagicMock()
        chain_end.__iter__ = lambda self: iter([])
        mid = MagicMock()
        mid.exclude.return_value = chain_end
        root = MagicMock()
        root.exclude.return_value = mid
        mock_filter.return_value = root
        factory = APIRequestFactory()
        request = factory.post("/api/auth/login-pin/", {"pin": "1234"}, format="json")
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RestaurantStaffPinLoginViewTests(SimpleTestCase):

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    def test_missing_device_id(self, _mock_pub, _mock_throttle):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "1234"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.get_or_create")
    def test_device_revoked(self, mock_goc, _mock_pub, _mock_throttle):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        device = MagicMock()
        device.is_revoked = True
        device.failed_attempts = 0
        device.locked_until = None
        mock_goc.return_value = (device, False)

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "1234", "device_id": "dev-1"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("code"), "device_revoked")

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.check_password", return_value=False)
    @patch("authentication.restaurant_auth.user_can_use_restaurant_pin", return_value=True)
    @patch("authentication.restaurant_auth.CustomUser.objects.filter")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.get_or_create")
    def test_new_device_no_matching_pin(
        self, mock_goc, mock_filter, _can_pin, _cp, _mock_pub, _mock_throttle
    ):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        device = SimpleNamespace(
            is_revoked=False,
            failed_attempts=0,
            locked_until=None,
        )
        device.save = MagicMock()
        mock_goc.return_value = (device, True)

        u = MagicMock()
        u.restaurant_pin_hash = "pbkdf2$"
        mock_qs = MagicMock()
        mock_qs.exclude.return_value = mock_qs
        mock_qs.__iter__ = lambda self: iter([u])
        mock_filter.return_value = mock_qs

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "1234", "device_id": "dev-new"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("code"), "invalid_pin")
        self.assertEqual(device.failed_attempts, 1)

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.restaurant_pin_is_expired", return_value=True)
    @patch("authentication.restaurant_auth.check_password", return_value=True)
    @patch("authentication.restaurant_auth.user_can_use_restaurant_pin", return_value=True)
    @patch("authentication.restaurant_auth.CustomUser.objects.filter")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.get_or_create")
    def test_pin_expired_on_device_login(
        self, mock_goc, mock_filter, _can_pin, _cp, _exp, _mock_pub, _mock_throttle
    ):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        user = MagicMock()
        user.is_active = True
        user.terminated = False
        user.restaurant_pin_hash = "x"
        mock_qs = MagicMock()
        mock_qs.exclude.return_value = mock_qs
        mock_qs.__iter__ = lambda self: iter([user])
        mock_filter.return_value = mock_qs

        device = MagicMock()
        device.is_revoked = False
        device.failed_attempts = 0
        device.locked_until = None
        mock_goc.return_value = (device, False)

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "1234", "device_id": "dev-1"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("code"), "pin_expired")

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.restaurant_pin_is_expired", return_value=False)
    @patch("authentication.restaurant_auth.check_password", return_value=False)
    @patch("authentication.restaurant_auth.user_can_use_restaurant_pin", return_value=True)
    @patch("authentication.restaurant_auth.CustomUser.objects.filter")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.get_or_create")
    def test_wrong_pin_increments_failures(
        self, mock_goc, mock_filter, _can_pin, _cp, _exp, _mock_pub, _mock_throttle
    ):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        user = MagicMock()
        user.restaurant_pin_hash = "x"
        mock_qs = MagicMock()
        mock_qs.exclude.return_value = mock_qs
        mock_qs.__iter__ = lambda self: iter([user])
        mock_filter.return_value = mock_qs

        device = SimpleNamespace(
            is_revoked=False,
            failed_attempts=0,
            locked_until=None,
        )
        device.save = MagicMock()
        mock_goc.return_value = (device, False)

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "9999", "device_id": "dev-1"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(device.failed_attempts, 1)
        device.save.assert_called()

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.get_or_create")
    def test_locked_after_max_attempts(
        self, mock_goc, _mock_pub, _mock_throttle
    ):
        from authentication.restaurant_auth import RestaurantStaffPinLoginView

        device = MagicMock()
        device.is_revoked = False
        device.failed_attempts = 3
        device.locked_until = None
        mock_goc.return_value = (device, False)

        factory = APIRequestFactory()
        request = factory.post(
            "/api/auth/pin/",
            {"pin": "1234", "device_id": "dev-1"},
            format="json",
        )
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantStaffPinLoginView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("code"), "pin_locked")


class RestaurantPinDeviceContextViewTests(SimpleTestCase):
    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    def test_requires_device_id(self, _mock_pub, _mock_throttle):
        from authentication.restaurant_auth import RestaurantPinDeviceContextView

        factory = APIRequestFactory()
        request = factory.get("/api/auth/pin/device-context/")
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantPinDeviceContextView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.select_related")
    def test_returns_staff_name(self, mock_sel, _mock_pub, _mock_throttle):
        from authentication.restaurant_auth import RestaurantPinDeviceContextView

        user = MagicMock()
        user.is_active = True
        user.terminated = False
        user.full_name = "Alex Kwan"
        user.username = "alex"
        device = MagicMock()
        device.is_revoked = False
        device.user = user
        mock_sel.return_value.get.return_value = device

        factory = APIRequestFactory()
        request = factory.get("/api/auth/pin/device-context/?device_id=dev-1")
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantPinDeviceContextView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("staff_name"), "Alex Kwan")

    @patch("rest_framework.throttling.AnonRateThrottle.allow_request", return_value=True)
    @patch("authentication.restaurant_auth.get_public_schema_name", return_value="public")
    @patch("authentication.restaurant_auth.RestaurantStaffDevice.objects.select_related")
    def test_unknown_device(self, mock_sel, _mock_pub, _mock_throttle):
        from authentication.restaurant_auth import RestaurantPinDeviceContextView

        mock_sel.return_value.get.side_effect = RestaurantStaffDevice.DoesNotExist

        factory = APIRequestFactory()
        request = factory.get("/api/auth/pin/device-context/?device_id=missing")
        request.tenant = MagicMock(schema_name="tenant_x")
        response = RestaurantPinDeviceContextView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = json.loads(response.rendered_content.decode())
        self.assertEqual(body.get("staff_name"), "")
