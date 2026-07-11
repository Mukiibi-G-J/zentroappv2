from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from reports.services.base_report_service import BaseReportService


class ReportCacheKeyTests(SimpleTestCase):
    def test_cache_key_includes_tenant_schema(self):
        service = BaseReportService(company_id=42)
        with patch(
            "reports.services.base_report_service.connection"
        ) as mock_conn:
            mock_conn.schema_name = "hardwareworld"
            key = service.get_cache_key(
                "daily_profit", {"start_date": "2026-01-01", "end_date": "2026-01-31"}
            )
        self.assertTrue(key.startswith("report:hardwareworld:daily_profit:"))
        self.assertIn("company=42", key)

    def test_cache_pattern_matches_key_layout(self):
        service = BaseReportService()
        with patch(
            "reports.services.base_report_service.connection"
        ) as mock_conn:
            mock_conn.schema_name = "ekk"
            pattern = service.cache_pattern_for_report("inventory_value_movement")
        self.assertEqual(pattern, "report:ekk:inventory_value_movement:*")

    def test_invalidate_cache_uses_delete_pattern(self):
        service = BaseReportService()
        with patch(
            "reports.services.base_report_service.connection"
        ) as mock_conn:
            mock_conn.schema_name = "ekk"
            with patch(
                "reports.services.base_report_service.cache"
            ) as mock_cache:
                mock_cache.delete_pattern = MagicMock(return_value=3)
                removed = service.invalidate_cache("daily_profit")
        mock_cache.delete_pattern.assert_called_once_with("report:ekk:daily_profit:*")
        self.assertEqual(removed, 3)

    def test_invalidate_cache_noop_without_delete_pattern(self):
        service = BaseReportService()
        with patch(
            "reports.services.base_report_service.cache"
        ) as mock_cache:
            del mock_cache.delete_pattern
            removed = service.invalidate_cache("daily_profit")
        self.assertEqual(removed, 0)
