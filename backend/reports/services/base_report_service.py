"""
Base Report Service
Provides common functionality for all report types including caching and data retrieval.
"""

from datetime import date, datetime
from django.core.cache import cache
from django.db import connection
from django.db.models import QuerySet
from typing import Dict, Any, Optional
import time

from ..utils.calculations import calculate_growth_percentage, calculate_profit_margin
from ..utils.formatters import validate_date_range, get_date_range


class BaseReportService:
    """
    Base class for all report generation services.
    Provides caching, validation, and common query patterns.
    """

    # Default cache TTL in seconds
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, company_id: Optional[int] = None):
        self.company_id = company_id
        self.execution_start = None

    def start_timer(self):
        """Start execution timer for performance tracking"""
        self.execution_start = time.time()

    def get_execution_time(self) -> int:
        """Get execution time in milliseconds"""
        if self.execution_start is None:
            return 0
        return int((time.time() - self.execution_start) * 1000)

    def get_cache_key(self, report_type: str, params: Dict[str, Any]) -> str:
        """
        Generate cache key for report data.

        Args:
            report_type: Type of report (e.g., 'daily_profit')
            params: Report parameters (date, filters, etc.)

        Returns:
            Cache key string
        """
        # Sort params for consistent cache keys
        sorted_params = sorted(params.items())
        params_str = "_".join([f"{k}={v}" for k, v in sorted_params])

        company_suffix = f"_company={self.company_id}" if self.company_id else ""
        schema = getattr(connection, "schema_name", None) or "public"
        return f"report:{schema}:{report_type}:{params_str}{company_suffix}"

    def get_cached_report(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached report data.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None
        """
        return cache.get(cache_key)

    def cache_report(
        self, cache_key: str, data: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Cache report data.

        Args:
            cache_key: Cache key
            data: Report data to cache
            ttl: Time-to-live in seconds (default: self.CACHE_TTL)
        """
        if ttl is None:
            ttl = self.CACHE_TTL

        cache.set(cache_key, data, timeout=ttl)

    def cache_pattern_for_report(self, report_type: str) -> str:
        """Logical cache key pattern for one report type in the current tenant schema."""
        schema = getattr(connection, "schema_name", None) or "public"
        return f"report:{schema}:{report_type}:*"

    def invalidate_cache(self, report_type: str) -> int:
        """
        Invalidate all cached reports of a specific type for the current tenant.

        Uses Django RedisCache.delete_pattern (SCAN), not blocking KEYS.

        Returns:
            Number of keys removed, or 0 if the backend does not support pattern delete.
        """
        pattern = self.cache_pattern_for_report(report_type)
        delete_pattern = getattr(cache, "delete_pattern", None)
        if delete_pattern is None:
            return 0
        try:
            return int(delete_pattern(pattern))
        except Exception:
            return 0

    @staticmethod
    def parse_date(date_str: Optional[str], default: Optional[date] = None) -> date:
        """
        Parse date string to date object.

        Args:
            date_str: Date string in YYYY-MM-DD format
            default: Default date if date_str is None

        Returns:
            Date object
        """
        if date_str is None:
            return default or date.today()

        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")

    @staticmethod
    def validate_filters(filters: Dict[str, Any]) -> bool:
        """
        Validate report filters.

        Args:
            filters: Dictionary of filter parameters

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        # Validate date range if present
        if "start_date" in filters and "end_date" in filters:
            start = filters["start_date"]
            end = filters["end_date"]

            if isinstance(start, str):
                start = datetime.strptime(start, "%Y-%m-%d").date()
            if isinstance(end, str):
                end = datetime.strptime(end, "%Y-%m-%d").date()

            validate_date_range(start, end)

        return True

    def format_response(
        self,
        report_type: str,
        data: Dict[str, Any],
        period: Dict[str, Any],
        cached: bool = False,
    ) -> Dict[str, Any]:
        """
        Format standard report response.

        Args:
            report_type: Type of report
            data: Report data
            period: Period information (start_date, end_date, etc.)
            cached: Whether data was served from cache

        Returns:
            Formatted response dictionary
        """
        return {
            "report_type": report_type,
            "period": period,
            "data": data,
            "generated_at": datetime.now().isoformat(),
            "cached": cached,
            "execution_time_ms": self.get_execution_time(),
        }
