from datetime import datetime, timezone as dt_timezone

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response


class DeltaSyncMixin:
    """Paginated delta pull by updated_at for models inheriting BaseModel."""

    default_page_size = 500
    max_page_size = 1000

    def parse_updated_since(self, request):
        raw = (request.query_params.get("updated_since") or "").strip()
        if not raw:
            return datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
        parsed = parse_datetime(raw)
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                parsed = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, dt_timezone.utc)
        return parsed

    def get_page_params(self, request):
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get("page_size", self.default_page_size))
        except (TypeError, ValueError):
            page_size = self.default_page_size
        page_size = min(max(1, page_size), self.max_page_size)
        return page, page_size

    def delta_queryset(self, queryset, updated_since):
        return queryset.filter(updated_at__gt=updated_since).order_by("updated_at", "pk")

    def build_delta_response(self, queryset, page, page_size, serialize_fn):
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        page_qs = list(queryset[start:end])
        results = [serialize_fn(obj) for obj in page_qs]
        max_updated = None
        for obj in page_qs:
            ts = getattr(obj, "updated_at", None)
            if ts and (max_updated is None or ts > max_updated):
                max_updated = ts
        if max_updated is None:
            max_updated = timezone.now()
        has_more = end < total
        return Response(
            {
                "results": results,
                "has_more": has_more,
                "max_updated_at": max_updated.isoformat(),
                "count": len(results),
                "total": total,
                "page": page,
            }
        )
