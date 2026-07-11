from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class DeltaSyncMixinTests(SimpleTestCase):
    def test_parse_updated_since_default(self):
        from sync.mixins import DeltaSyncMixin

        mixin = DeltaSyncMixin()
        request = MagicMock()
        request.query_params = {}
        parsed = mixin.parse_updated_since(request)
        self.assertEqual(parsed.year, 1970)

    def test_parse_updated_since_iso(self):
        from sync.mixins import DeltaSyncMixin

        mixin = DeltaSyncMixin()
        request = MagicMock()
        request.query_params = {"updated_since": "2026-01-15T10:00:00Z"}
        parsed = mixin.parse_updated_since(request)
        self.assertEqual(parsed.year, 2026)


class SyncPingShapeTests(SimpleTestCase):
    def test_ping_response_keys(self):
        from django.test import RequestFactory
        from sync.views import sync_ping

        request = RequestFactory().get("/api/sync/ping/")
        response = sync_ping(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.data)
        self.assertIn("server_time", response.data)
