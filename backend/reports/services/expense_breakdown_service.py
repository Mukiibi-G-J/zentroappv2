"""
Expense Breakdown Report Service
Analyzes expenses by category with period comparisons and drill-down capability.
"""
from datetime import date, timedelta
from django.db.models import Sum, Count
from decimal import Decimal

from expenses.models import Expense
from .base_report_service import BaseReportService
from ..utils.calculations import calculate_growth_percentage


class ExpenseBreakdownService(BaseReportService):
    """Service for generating expense breakdown reports"""

    CACHE_TTL = 900  # 15 minutes

    def generate_report(
        self,
        start_date: date,
        end_date: date,
        drill_down_type: str = None,
        branch=None,
    ) -> dict:
        """
        Generate expense breakdown report by category.
        
        Args:
            start_date: Start date
            end_date: End date
            drill_down_type: Specific expense type to drill down into (optional)
            branch: Optional DimensionValue to filter by branch
        
        Returns:
            Dictionary with report data
        """
        self.start_timer()

        # Get current period breakdown
        expense_breakdown = self._get_expense_breakdown(start_date, end_date, branch=branch)
        
        # Calculate total expenses
        total_expenses = sum(e["total_amount"] for e in expense_breakdown)
        total_count = sum(e["expense_count"] for e in expense_breakdown)

        # Get previous period data for comparison
        days_diff = (end_date - start_date).days + 1
        prev_start = start_date - timedelta(days=days_diff)
        prev_end = end_date - timedelta(days=days_diff)
        
        prev_breakdown = self._get_expense_breakdown(prev_start, prev_end, branch=branch)
        prev_total = sum(e["total_amount"] for e in prev_breakdown)

        # Calculate period-over-period change
        period_change = calculate_growth_percentage(total_expenses, prev_total)

        # Get drill-down details if requested
        drill_down_data = None
        if drill_down_type:
            drill_down_data = self._get_drill_down_details(
                start_date, end_date, drill_down_type, branch=branch
            )

        # Calculate average daily expense
        avg_daily_expense = total_expenses / days_diff if days_diff > 0 else 0

        # Compile report data
        report_data = {
            "summary": {
                "total_expenses": float(total_expenses),
                "total_count": total_count,
                "category_count": len(expense_breakdown),
                "avg_daily_expense": round(avg_daily_expense, 2),
                "period_comparison": {
                    "previous_total": float(prev_total),
                    "change_percentage": round(period_change, 2),
                },
            },
            "breakdown": expense_breakdown,
            "drill_down": drill_down_data,
        }

        return self.format_response(
            report_type="expense_breakdown",
            data=report_data,
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            cached=False
        )

    def _get_expense_breakdown(self, start_date: date, end_date: date, branch=None) -> list:
        """Get expense breakdown by type with percentages"""
        qs = Expense.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted"
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)
        expenses_by_type = (
            qs
            .values("expense_type__name", "expense_type_id")
            .annotate(
                total_amount=Sum("amount"),
                expense_count=Count("id")
            )
            .order_by("-total_amount")
        )

        # Calculate total for percentages
        total_expenses = sum(
            float(e["total_amount"]) for e in expenses_by_type if e["total_amount"]
        )

        result = []
        for expense in expenses_by_type:
            amount = float(expense["total_amount"] or 0)
            percentage = (amount / total_expenses) * 100 if total_expenses > 0 else 0
            
            result.append({
                "expense_type_id": expense["expense_type_id"],
                "expense_type_name": expense["expense_type__name"] or "Uncategorized",
                "total_amount": amount,
                "expense_count": expense["expense_count"],
                "percentage": round(percentage, 1),
            })

        return result

    def _get_drill_down_details(
        self, start_date: date, end_date: date, expense_type_id: str, branch=None
    ) -> list:
        """Get detailed transactions for a specific expense type"""
        qs = Expense.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted",
            expense_type_id=expense_type_id
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)
        expenses = qs.values(
            "id",
            "document_no",
            "posting_date",
            "description",
            "amount",
            "payment_method__description"
        ).order_by("-posting_date")

        result = []
        for expense in expenses:
            result.append({
                "id": expense["id"],
                "document_no": expense["document_no"],
                "date": expense["posting_date"].isoformat(),
                "description": expense["description"] or "",
                "amount": float(expense["amount"] or 0),
                "payment_method": expense["payment_method__description"] or "N/A",
            })

        return result

