from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from authentication.models import CustomUser
from settings.models import MobileAppUserSettings


class MobileAppSettingsApiTests(APITestCase):
    def setUp(self):
        self.url = reverse("settings:mobile-settings")
        self.user = CustomUser.objects.create_user(
            email="mobile@test.com",
            username="mobile_user",
            full_name="Mobile User",
            phone_number="+256700000001",
            password="Password123!",
            is_verified=True,
            is_staff=True,
            is_superuser=True,
        )
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_creates_defaults(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["searchMode"], "barcode")
        self.assertFalse(response.data["barcodeScannerEnabled"])
        self.assertTrue(response.data["barcodeBeepEnabled"])
        self.assertEqual(response.data["printer"]["type"], "none")
        self.assertEqual(response.data["printer"]["paperWidth"], "58")
        self.assertEqual(response.data["printer"]["copies"], 1)
        self.assertEqual(
            response.data["tenant"]["currentTenant"], connection.tenant.schema_name
        )
        self.assertTrue(MobileAppUserSettings.objects.filter(user=self.user).exists())

    def test_patch_updates_values(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.get(self.url)
        payload = {
            "searchMode": "realtime",
            "barcodeScannerEnabled": False,
            "barcodeBeepEnabled": False,
            "printer": {
                "type": "sunmi",
                "deviceName": "Sunmi V2",
                "macAddress": "",
                "paperWidth": "80",
                "copies": 2,
            },
        }
        response = self.client.patch(
            self.url,
            payload,
            format="json",
            HTTP_IF_UNMODIFIED_SINCE=first.data["updatedAt"],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["searchMode"], "realtime")
        self.assertFalse(response.data["barcodeScannerEnabled"])
        self.assertFalse(response.data["barcodeBeepEnabled"])
        self.assertEqual(response.data["printer"]["type"], "sunmi")
        self.assertEqual(response.data["printer"]["paperWidth"], "80")
        self.assertEqual(response.data["printer"]["copies"], 2)

    def test_patch_rejects_invalid_search_mode(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.url, {"searchMode": "bad_mode"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_patch_rejects_non_boolean_flags(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.url,
            {"barcodeScannerEnabled": "true"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_patch_rejects_invalid_bluetooth_printer(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.url,
            {
                "printer": {
                    "type": "bluetooth",
                    "deviceName": "",
                    "macAddress": "xx",
                    "paperWidth": "58",
                    "copies": 1,
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_patch_conflict_with_stale_updated_at(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.get(self.url)
        stale_updated_at = first.data["updatedAt"]
        self.client.patch(
            self.url,
            {"searchMode": "realtime"},
            format="json",
            HTTP_IF_UNMODIFIED_SINCE=stale_updated_at,
        )
        response = self.client.patch(
            self.url,
            {"searchMode": "barcode"},
            format="json",
            HTTP_IF_UNMODIFIED_SINCE=stale_updated_at,
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "settings_conflict")

    def test_patch_allowed_for_user_without_admin_roles(self):
        """Mobile prefs are per-user; POS users without edit_settings may PATCH their own."""
        limited_user = CustomUser.objects.create_user(
            email="limited@test.com",
            username="limited_user",
            full_name="Limited User",
            phone_number="+256700000002",
            password="Password123!",
            is_verified=True,
        )
        self.client.force_authenticate(user=limited_user)
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        response = self.client.patch(
            self.url,
            {"searchMode": "realtime"},
            format="json",
            HTTP_IF_UNMODIFIED_SINCE=first.data["updatedAt"],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["searchMode"], "realtime")
