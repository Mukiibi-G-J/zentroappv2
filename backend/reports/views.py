from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from authentication.authentication import (
    JWTAuthenticationWithRevocationChecks as JWTAuthentication,
)
from rest_framework.authentication import SessionAuthentication
from datetime import datetime, date, timedelta
import time

from .models import ScheduledReport, ReportLog
from .serializers import ScheduledReportSerializer, ReportLogSerializer
from .services.daily_profit_service import DailyProfitService
from .services.weekly_summary_service import WeeklySummaryService
from .services.monthly_summary_service import MonthlySummaryService
from .services.product_profitability_service import ProductProfitabilityService
from .services.expense_breakdown_service import ExpenseBreakdownService
from .services.inventory_value_movement_service import InventoryValueMovementService
from .services.inventory_value_movement_export import (
    build_inventory_value_movement_excel,
    build_inventory_value_movement_pdf,
)
from .services.inventory_transaction_detail_service import (
    InventoryTransactionDetailService,
)
from .services.inventory_transaction_detail_export import (
    build_inventory_transaction_detail_excel,
    build_inventory_transaction_detail_pdf,
)
from .services.base_report_service import BaseReportService
from dimension.branch_filter import get_branch_for_request
from django.http import HttpResponse
from django.db import connection
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from items.models import ItemLedgerEntries
from django.db.models import Sum
from django.utils import timezone


class ReportsViewSet(viewsets.ViewSet):
    """
    ViewSet for generating various business reports.

    Endpoints:
    - daily_profit: Daily profit report
    - weekly_summary: Weekly performance summary
    - monthly_summary: Monthly business overview
    - profitable_products: Product profitability analysis
    - expense_breakdown: Expense category breakdown
    """

    permission_classes = [IsAuthenticated]
    # JWT before session: SPA sends Bearer token; session-first + admin cookie → CSRF 403 (shows as CORS in DevTools).
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    _ALL_BRANCHES = "all"

    def _get_branch(self, request):
        """
        Resolve the branch DimensionValue for the current request.
        Returns:
            DimensionValue  – filter by that branch
            "all"           – explicitly all branches, no filtering
            None            – multi-branch disabled, no filtering
        """
        from financials.models import GeneralLedgerSetup
        from dimension.models import DimensionValue

        gl_setup = GeneralLedgerSetup.objects.first()
        if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
            return None

        branch_param = request.query_params.get("branch")
        if branch_param is not None:
            if branch_param == "all":
                return self._ALL_BRANCHES
            try:
                return DimensionValue.objects.filter(pk=int(branch_param)).first()
            except (ValueError, TypeError):
                return self._ALL_BRANCHES

        return get_branch_for_request(request)

    @staticmethod
    def _branch_for_query(branch):
        """Convert _get_branch result to a value suitable for service calls (None or DimensionValue)."""
        if branch == ReportsViewSet._ALL_BRANCHES or branch is None:
            return None
        return branch

    @staticmethod
    def _branch_label(branch_raw, branch_for_query):
        if branch_raw == ReportsViewSet._ALL_BRANCHES:
            return "All Branches"
        if branch_for_query is not None:
            return (
                getattr(branch_for_query, "description", None)
                or getattr(branch_for_query, "code", None)
                or str(branch_for_query.id)
            )
        return ""

    @staticmethod
    def _branch_cache_key(branch):
        """Return a string to include in cache keys so each branch gets its own cache."""
        if branch is None:
            return None
        if branch == ReportsViewSet._ALL_BRANCHES:
            return "all"
        return str(branch.id)

    @staticmethod
    def _report_cache_ttl(end_date: date) -> int:
        """Shorter TTL when the period includes today (live postings)."""
        if end_date >= date.today():
            return 300  # 5 minutes
        return 1800  # 30 minutes for closed periods

    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _log_report(
        self, report_type, user, filters, execution_time, cached, ip, export_format=None
    ):
        """Log report generation for audit trail"""
        try:
            ReportLog.objects.create(
                report_type=report_type,
                generated_by=user,
                filters_applied=filters,
                export_format=export_format,
                execution_time_ms=execution_time,
                cached=cached,
                ip_address=ip,
            )
        except Exception as e:
            # Log errors but don't fail the request
            print(f"Error logging report generation: {str(e)}")

    @action(detail=False, methods=["get"], url_path="daily-profit")
    def daily_profit(self, request):
        """
        Get daily profit report showing sales, expenses, and net profit.

        Query params:
        - date: YYYY-MM-DD (default: today)
        """
        start_time = time.time()

        # Check permission
        has_permission, source = request.user.check_object_permission(10301, "read")
        if not has_permission:
            return Response(
                {"error": "Insufficient permissions to view Daily Profit Report"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get date from query params
            date_str = request.query_params.get("date")
            report_date = BaseReportService.parse_date(date_str, default=date.today())
            branch_raw = self._get_branch(request)

            # Generate cache key
            service = DailyProfitService()
            cache_params = {"date": report_date.isoformat()}
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("daily_profit", cache_params)

            # Try to get from cache
            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True

                # Log the report generation
                self._log_report(
                    report_type="daily_profit",
                    user=request.user,
                    filters={"date": report_date.isoformat()},
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )

                return Response(cached_data)

            # Generate report
            report_data = service.generate_report(
                report_date, branch=self._branch_for_query(branch_raw)
            )

            # Cache the result
            service.cache_report(cache_key, report_data, ttl=300)  # 5 minutes

            # Log the report generation
            self._log_report(
                report_type="daily_profit",
                user=request.user,
                filters={"date": report_date.isoformat()},
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating daily profit report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="weekly-summary")
    def weekly_summary(self, request):
        """
        Get weekly summary report with trends and top products.

        Query params:
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        """
        start_time = time.time()

        # Check permission
        has_permission, source = request.user.check_object_permission(10302, "read")
        if not has_permission:
            return Response(
                {"error": "Insufficient permissions to view Weekly Summary Report"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get date range from query params
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            # Default to current week (Monday to Sunday)
            if not start_date_str or not end_date_str:
                today = date.today()
                start_date = today - timedelta(days=today.weekday())  # Monday
                end_date = start_date + timedelta(days=6)  # Sunday
            else:
                start_date = BaseReportService.parse_date(start_date_str)
                end_date = BaseReportService.parse_date(end_date_str)

            branch_raw = self._get_branch(request)

            # Generate cache key
            service = WeeklySummaryService()
            cache_params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("weekly_summary", cache_params)

            # Try to get from cache
            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True

                self._log_report(
                    report_type="weekly_summary",
                    user=request.user,
                    filters={
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    },
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )

                return Response(cached_data)

            # Generate report
            report_data = service.generate_report(
                start_date, end_date, branch=self._branch_for_query(branch_raw)
            )

            # Cache the result
            service.cache_report(cache_key, report_data, ttl=900)  # 15 minutes

            # Log the report generation
            self._log_report(
                report_type="weekly_summary",
                user=request.user,
                filters={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating weekly summary report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        """
        Get monthly summary report with KPIs and comparisons.

        Query params:
        - month: YYYY-MM (default: current month)
        """
        start_time = time.time()

        # Check permission
        has_permission, source = request.user.check_object_permission(10303, "read")
        if not has_permission:
            return Response(
                {"error": "Insufficient permissions to view Monthly Summary Report"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get month from query params (default: current month)
            month_str = request.query_params.get("month")
            if not month_str:
                today = date.today()
                month_str = today.strftime("%Y-%m")

            # Validate format
            try:
                year, month = map(int, month_str.split("-"))
                if not (1 <= month <= 12):
                    raise ValueError("Month must be between 1 and 12")
            except (ValueError, AttributeError):
                return Response(
                    {"error": "Invalid month format. Expected YYYY-MM"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            branch_raw = self._get_branch(request)

            # Generate cache key
            service = MonthlySummaryService()
            cache_params = {"month": month_str}
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("monthly_summary", cache_params)

            # Try to get from cache
            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True

                self._log_report(
                    report_type="monthly_summary",
                    user=request.user,
                    filters={"month": month_str},
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )

                return Response(cached_data)

            # Generate report
            report_data = service.generate_report(
                month_str, branch=self._branch_for_query(branch_raw)
            )

            # Cache the result
            service.cache_report(cache_key, report_data, ttl=3600)  # 1 hour

            # Log the report generation
            self._log_report(
                report_type="monthly_summary",
                user=request.user,
                filters={"month": month_str},
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating monthly summary report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="profitable-products")
    def profitable_products(self, request):
        """
        Get product profitability report.

        Query params:
        - start_date, end_date: Date range
        - category: Filter by product category
        - product_type: Filter by product/service
        - sort_by: profit, margin, revenue, units
        - page: Pagination
        """
        start_time = time.time()

        # Check permission
        has_permission, source = request.user.check_object_permission(10304, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions to view Product Profitability Report"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get query parameters
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")
            category = request.query_params.get("category")
            product_type = request.query_params.get("product_type")
            sort_by = request.query_params.get("sort_by", "profit")
            page = int(request.query_params.get("page", 1))

            # Default to current month if no dates provided
            if not start_date_str or not end_date_str:
                today = date.today()
                start_date = today.replace(day=1)
                end_date = today
            else:
                start_date = BaseReportService.parse_date(start_date_str)
                end_date = BaseReportService.parse_date(end_date_str)

            branch_raw = self._get_branch(request)

            # Generate cache key
            service = ProductProfitabilityService()
            cache_params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "category": category or "all",
                "product_type": product_type or "all",
                "sort_by": sort_by,
                "page": page,
            }
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("product_profitability", cache_params)

            # Try to get from cache
            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True

                self._log_report(
                    report_type="product_profitability",
                    user=request.user,
                    filters={
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "category": category,
                        "sort_by": sort_by,
                    },
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )

                return Response(cached_data)

            # Generate report
            report_data = service.generate_report(
                start_date=start_date,
                end_date=end_date,
                category=category,
                product_type=product_type,
                sort_by=sort_by,
                page=page,
                branch=self._branch_for_query(branch_raw),
            )

            # Cache the result
            service.cache_report(cache_key, report_data, ttl=900)  # 15 minutes

            # Log the report generation
            self._log_report(
                report_type="product_profitability",
                user=request.user,
                filters={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "category": category,
                    "sort_by": sort_by,
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating product profitability report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="expense-breakdown")
    def expense_breakdown(self, request):
        """
        Get expense breakdown by category.

        Query params:
        - start_date, end_date: Date range
        - drill_down_type: Expense type ID for detailed view (optional)
        """
        start_time = time.time()

        # Check permission
        has_permission, source = request.user.check_object_permission(10305, "read")
        if not has_permission:
            return Response(
                {"error": "Insufficient permissions to view Expense Breakdown Report"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get date range from query params
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")
            drill_down_type = request.query_params.get("drill_down_type")

            # Default to current month if no dates provided
            if not start_date_str or not end_date_str:
                today = date.today()
                start_date = today.replace(day=1)
                end_date = today
            else:
                start_date = BaseReportService.parse_date(start_date_str)
                end_date = BaseReportService.parse_date(end_date_str)

            branch_raw = self._get_branch(request)

            # Generate cache key
            service = ExpenseBreakdownService()
            cache_params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "drill_down": drill_down_type or "none",
            }
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("expense_breakdown", cache_params)

            # Try to get from cache
            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True

                self._log_report(
                    report_type="expense_breakdown",
                    user=request.user,
                    filters={
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    },
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )

                return Response(cached_data)

            # Generate report
            report_data = service.generate_report(
                start_date=start_date,
                end_date=end_date,
                drill_down_type=drill_down_type,
                branch=self._branch_for_query(branch_raw),
            )

            # Cache the result
            service.cache_report(cache_key, report_data, ttl=900)  # 15 minutes

            # Log the report generation
            self._log_report(
                report_type="expense_breakdown",
                user=request.user,
                filters={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating expense breakdown report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="inventory-expiry-pdf")
    def inventory_expiry_pdf(self, request):
        """
        Generate Inventory Expiry PDF
        Query params:
          - expiry_from (YYYY-MM-DD) optional
          - expiry_to (YYYY-MM-DD) optional
          - include_zero (bool) default false
        """
        start_time = time.time()

        # Permission: check dedicated Expiry Report page id
        has_permission, source = request.user.check_object_permission(10506, "read")
        # Allow superusers regardless; otherwise enforce page permission
        if not has_permission and not getattr(request.user, "is_superuser", False):
            return Response(
                {"error": "Insufficient permissions to view Inventory Expiry Report"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            expiry_from = request.query_params.get("expiry_from")
            expiry_to = request.query_params.get("expiry_to")
            include_zero = request.query_params.get(
                "include_zero", "false"
            ).lower() in [
                "1",
                "true",
                "yes",
            ]
            # Days threshold for "expiring soon"
            soon_days_raw = request.query_params.get("soon_days")
            try:
                soon_days = int(soon_days_raw) if soon_days_raw is not None else 30
            except ValueError:
                soon_days = 30

            qs = ItemLedgerEntries.objects.select_related("item").all()
            branch = self._branch_for_query(self._get_branch(request))
            if branch:
                qs = qs.filter(global_dimension_1=branch)
            if expiry_from:
                qs = qs.filter(expiry_date__gte=expiry_from)
            if expiry_to:
                qs = qs.filter(expiry_date__lte=expiry_to)
            if not include_zero:
                qs = qs.filter(remaining_quantity__gt=0)
            qs = qs.order_by("expiry_date", "item__item_name", "lot_no")

            # Aggregate totals
            total_remaining = (
                qs.aggregate(total=Sum("remaining_quantity"))["total"] or 0
            )

            # Build PDF
            response = HttpResponse(content_type="application/pdf")
            filename = "inventory-expiry-report.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            doc = SimpleDocTemplate(
                response,
                pagesize=A4,
                leftMargin=18 * mm,
                rightMargin=18 * mm,
                topMargin=16 * mm,
                bottomMargin=16 * mm,
            )
            story = []
            styles = getSampleStyleSheet()

            title = "Inventory Expiry Report"
            filters_text = []
            if expiry_from:
                filters_text.append(f"From: {expiry_from}")
            if expiry_to:
                filters_text.append(f"To: {expiry_to}")
            if include_zero:
                filters_text.append("Including zero quantity")
            filters_text.append(f"Expiring soon threshold: {soon_days} days")

            story.append(Paragraph(title, styles["Title"]))
            story.append(
                Paragraph(" ".join(filters_text) or "All expiries", styles["Normal"])
            )
            story.append(
                Paragraph(
                    f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 6 * mm))

            data = [["Item", "Lot No", "Expiry Date", "Days Left", "Remaining Qty"]]
            row_styles = []
            today = timezone.now().date()
            for idx, entry in enumerate(qs, start=1):
                item_name = getattr(entry.item, "item_name", "")
                lot = entry.lot_no or "-"
                if entry.expiry_date:
                    days_left = (entry.expiry_date - today).days
                    expiry_str = entry.expiry_date.strftime("%Y-%m-%d")
                else:
                    days_left = None
                    expiry_str = "-"
                data.append(
                    [
                        item_name,
                        lot,
                        expiry_str,
                        "-" if days_left is None else f"{days_left}",
                        f"{entry.remaining_quantity}",
                    ]
                )
                # Color coding
                if days_left is None:
                    # no color
                    pass
                elif days_left < 0:
                    # expired: light red
                    row_styles.append(
                        ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fde7e7"))
                    )
                elif days_left <= soon_days:
                    # soon: light yellow
                    row_styles.append(
                        ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fff8db"))
                    )
                else:
                    # ok: very light green
                    row_styles.append(
                        ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#e9f8ef"))
                    )

            # handle empty
            if len(data) == 1:
                data.append(["No data", "-", "-", "-", "-"])

            table = Table(data, colWidths=[60 * mm, 28 * mm, 30 * mm, 22 * mm, 28 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3ff")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f3fff")),
                        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.whitesmoke, colors.whitesmoke],
                        ),
                    ]
                )
            )
            # Apply row color styles
            for style_cmd in row_styles:
                table.setStyle(TableStyle([style_cmd]))
            story.append(table)
            story.append(Spacer(1, 4 * mm))
            story.append(
                Paragraph(
                    f"Total Remaining Quantity: {total_remaining}", styles["Heading4"]
                )
            )

            doc.build(story)

            # Log
            self._log_report(
                report_type="inventory_expiry_pdf",
                user=request.user,
                filters={
                    "expiry_from": expiry_from,
                    "expiry_to": expiry_to,
                    "include_zero": include_zero,
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
                export_format="pdf",
            )

            return response
        except Exception as e:
            return Response(
                {"error": f"Error generating inventory expiry report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _inventory_value_movement_permission_denied(self, request):
        has_permission, source = request.user.check_object_permission(10303, "read")
        if has_permission:
            return None
        return Response(
            {
                "error": "Insufficient permissions to view Inventory Value Movement Report"
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=["get"], url_path="inventory-value-movement")
    def inventory_value_movement(self, request):
        """
        Get inventory value movement report.

        Query params:
        - period_type: daily | monthly | custom (default: daily)
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        """
        start_time = time.time()

        denied = self._inventory_value_movement_permission_denied(request)
        if denied:
            return denied

        try:
            branch_raw = self._get_branch(request)
            branch = self._branch_for_query(branch_raw)
            start_date, end_date, period_type = (
                InventoryValueMovementService.parse_report_window(request, branch)
            )
            service = InventoryValueMovementService()

            cache_params = {
                "v": "15",
                "period_type": period_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            if InventoryValueMovementService.is_all_time_request(request):
                cache_params["all_time"] = "1"
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = service.get_cache_key("inventory_value_movement", cache_params)

            if request.query_params.get("refresh", "").lower() in ("1", "true", "yes"):
                service.invalidate_cache("inventory_value_movement")

            cached_data = service.get_cached_report(cache_key)
            if cached_data:
                cached_data["cached"] = True
                self._log_report(
                    report_type="inventory_value_movement",
                    user=request.user,
                    filters=cache_params,
                    execution_time=int((time.time() - start_time) * 1000),
                    cached=True,
                    ip=self._get_client_ip(request),
                )
                return Response(cached_data)

            report_data = service.generate_report(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type,
                branch=branch,
            )
            service.cache_report(
                cache_key, report_data, ttl=self._report_cache_ttl(end_date)
            )

            self._log_report(
                report_type="inventory_value_movement",
                user=request.user,
                filters=cache_params,
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
            )

            return Response(report_data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "error": f"Error generating inventory value movement report: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="inventory-value-movement-pdf")
    def inventory_value_movement_pdf(self, request):
        """Download Inventory Value Movement report as PDF."""
        start_time = time.time()
        denied = self._inventory_value_movement_permission_denied(request)
        if denied:
            return denied

        try:
            branch_raw = self._get_branch(request)
            branch = self._branch_for_query(branch_raw)
            start_date, end_date, period_type = (
                InventoryValueMovementService.parse_report_window(request, branch)
            )
            service = InventoryValueMovementService()
            report_data = service.generate_report(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type,
                branch=branch,
            )
            report_data["export_details"] = service.build_export_details(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type,
                opening_value=report_data["data"]["summary"]["opening_value"],
                buckets=report_data["data"]["buckets"],
                branch=branch,
            )
            branch_label = self._branch_label(branch_raw, branch)
            response = build_inventory_value_movement_pdf(report_data, branch_label)

            self._log_report(
                report_type="inventory_value_movement_pdf",
                user=request.user,
                filters={
                    "period_type": period_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    **(
                        {"all_time": "1"}
                        if InventoryValueMovementService.is_all_time_request(request)
                        else {}
                    ),
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
                export_format="pdf",
            )
            return response
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating inventory value movement PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="inventory-value-movement-excel")
    def inventory_value_movement_excel(self, request):
        """Download Inventory Value Movement report as Excel."""
        start_time = time.time()
        denied = self._inventory_value_movement_permission_denied(request)
        if denied:
            return denied

        try:
            branch_raw = self._get_branch(request)
            branch = self._branch_for_query(branch_raw)
            start_date, end_date, period_type = (
                InventoryValueMovementService.parse_report_window(request, branch)
            )
            service = InventoryValueMovementService()
            report_data = service.generate_report(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type,
                branch=branch,
            )
            report_data["export_details"] = service.build_export_details(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type,
                opening_value=report_data["data"]["summary"]["opening_value"],
                buckets=report_data["data"]["buckets"],
                branch=branch,
            )
            branch_label = self._branch_label(branch_raw, branch)
            response = build_inventory_value_movement_excel(report_data, branch_label)

            self._log_report(
                report_type="inventory_value_movement_excel",
                user=request.user,
                filters={
                    "period_type": period_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    **(
                        {"all_time": "1"}
                        if InventoryValueMovementService.is_all_time_request(request)
                        else {}
                    ),
                },
                execution_time=int((time.time() - start_time) * 1000),
                cached=False,
                ip=self._get_client_ip(request),
                export_format="excel",
            )
            return response
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generating inventory value movement Excel: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _inventory_transaction_detail_permission_denied(self, request):
        has_permission, source = request.user.check_object_permission(10507, "read")
        if has_permission:
            return None
        return Response(
            {
                "error": "Insufficient permissions to view Inventory Transaction Detail Report"
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @staticmethod
    def _tenant_company_name():
        try:
            tenant = getattr(connection, "tenant", None)
            return getattr(tenant, "name", "") or ""
        except Exception:
            return ""

    @action(detail=False, methods=["get"], url_path="inventory-transaction-detail")
    def inventory_transaction_detail(self, request):
        """
        Inventory transaction detail per item with running qty/cost balances.

        Query params: start_date, end_date, item_no, entry_type, branch,
        only_with_activity (true), export (excel | pdf).
        Branch filter matches the Items list (global_dimension_1 only).
        Opening balance = current on-hand minus net quantity in the period (Items list basis).
        """
        start_time = time.time()
        denied = self._inventory_transaction_detail_permission_denied(request)
        if denied:
            return denied

        today = date.today()
        start_str = request.query_params.get(
            "start_date", today.replace(day=1).isoformat()
        )
        end_str = request.query_params.get("end_date", today.isoformat())
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item_no = request.query_params.get("item_no") or None
        entry_type = request.query_params.get("entry_type") or None
        only_with_activity = request.query_params.get(
            "only_with_activity", ""
        ).lower() in ("1", "true", "yes")
        export_fmt = request.query_params.get("export")

        branch_raw = self._get_branch(request)
        branch = self._branch_for_query(branch_raw)

        try:
            svc = InventoryTransactionDetailService()
            filters_applied = {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "item_no": item_no,
                "entry_type": entry_type,
                "branch": str(branch) if branch else None,
                "only_with_activity": only_with_activity,
            }
            cache_params = {"v": "2", **filters_applied}
            branch_key = self._branch_cache_key(branch_raw)
            if branch_key:
                cache_params["branch"] = branch_key
            cache_key = svc.get_cache_key(
                "inventory_transaction_detail", cache_params
            )

            report_data = None
            served_from_cache = False
            if not export_fmt:
                report_data = svc.get_cached_report(cache_key)
                if report_data:
                    served_from_cache = True
                    report_data = dict(report_data)
                    report_data["cached"] = True

            if report_data is None:
                report_data = svc.get_report(
                    start_date=start_date,
                    end_date=end_date,
                    branch=branch,
                    item_no=item_no,
                    entry_type=entry_type,
                    only_with_activity=only_with_activity,
                )
                if not export_fmt:
                    svc.cache_report(
                        cache_key,
                        report_data,
                        ttl=self._report_cache_ttl(end_date),
                    )

            elapsed_ms = int((time.time() - start_time) * 1000)
            company_name = self._tenant_company_name()

            if export_fmt == "excel":
                buf = build_inventory_transaction_detail_excel(
                    report_data,
                    company_name=company_name,
                    generated_by=str(request.user),
                )
                fname = f"inventory_transaction_detail_{start_date}_{end_date}.xlsx"
                self._log_report(
                    report_type="inventory_transaction_detail",
                    user=request.user,
                    filters=filters_applied,
                    execution_time=elapsed_ms,
                    cached=False,
                    ip=self._get_client_ip(request),
                    export_format="excel",
                )
                resp = HttpResponse(
                    buf.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                resp["Content-Disposition"] = f'attachment; filename="{fname}"'
                return resp

            if export_fmt == "pdf":
                buf = build_inventory_transaction_detail_pdf(
                    report_data,
                    company_name=company_name,
                    generated_by=str(request.user),
                )
                fname = f"inventory_transaction_detail_{start_date}_{end_date}.pdf"
                self._log_report(
                    report_type="inventory_transaction_detail",
                    user=request.user,
                    filters=filters_applied,
                    execution_time=elapsed_ms,
                    cached=False,
                    ip=self._get_client_ip(request),
                    export_format="pdf",
                )
                resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
                resp["Content-Disposition"] = f'attachment; filename="{fname}"'
                return resp

            self._log_report(
                report_type="inventory_transaction_detail",
                user=request.user,
                filters=filters_applied,
                execution_time=elapsed_ms,
                cached=served_from_cache,
                ip=self._get_client_ip(request),
            )
            return Response(report_data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "error": f"Error generating inventory transaction detail report: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for scheduled reports.
    Users can create, view, update, and delete their own scheduled reports.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    serializer_class = ScheduledReportSerializer
    queryset = ScheduledReport.objects.all()

    def get_queryset(self):
        """Filter to show only user's own scheduled reports"""
        return ScheduledReport.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)


class ReportLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view of report generation logs.
    For auditing and performance monitoring.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    serializer_class = ReportLogSerializer
    queryset = ReportLog.objects.all()

    def get_queryset(self):
        """Filter logs based on user permissions"""
        user = self.request.user

        # Admins see all logs
        if user.is_superuser or user.is_staff:
            return ReportLog.objects.all()

        # Regular users see only their own logs
        return ReportLog.objects.filter(generated_by=user)
