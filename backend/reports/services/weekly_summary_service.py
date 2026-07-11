"""
Weekly Summary Report Service
Generates weekly performance summary using G/L entries for accurate profit calculations.
"""
from datetime import date, timedelta
from django.db.models import Sum, Count, F
from decimal import Decimal

from financials.models import GeneralLedgerEntry, G_LAccount
from sales.models import SalesInvoice, SalesInvoiceLine
from expenses.models import Expense
from .base_report_service import BaseReportService
from ..utils.calculations import calculate_growth_percentage, calculate_profit_margin


class WeeklySummaryService(BaseReportService):
    """Service for generating weekly summary reports using G/L entries"""

    CACHE_TTL = 900  # 15 minutes

    def generate_report(self, start_date: date, end_date: date, branch=None) -> dict:
        """
        Generate weekly summary report using G/L entries.
        
        Args:
            start_date: Week start date
            end_date: Week end date
            branch: Optional DimensionValue to filter by branch
        
        Returns:
            Dictionary with report data
        """
        self.start_timer()

        # Get current week data from G/L
        current_data = self._get_gl_data(start_date, end_date, branch=branch)

        # Get previous week data for comparison
        days_diff = (end_date - start_date).days + 1
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days_diff - 1)
        previous_data = self._get_gl_data(prev_start, prev_end, branch=branch)

        # Calculate week-over-week changes
        revenue_change = calculate_growth_percentage(
            current_data["revenue"], previous_data["revenue"]
        )
        expense_change = calculate_growth_percentage(
            current_data["total_expenses"], previous_data["total_expenses"]
        )
        profit_change = calculate_growth_percentage(
            current_data["net_profit"], previous_data["net_profit"]
        )

        # Get top 5 products by revenue
        top_products = self._get_top_products(start_date, end_date, limit=5, branch=branch)

        # Get expense breakdown by type
        expense_breakdown = self._get_expense_breakdown(start_date, end_date, branch=branch)

        # Get daily breakdown for the week
        daily_breakdown = self._get_daily_breakdown(start_date, end_date, branch=branch)

        # Compile report data
        report_data = {
            "total_revenue": current_data["revenue"],
            "total_expenses": current_data["total_expenses"],
            "total_cogs": current_data["cogs"],
            "gross_profit": current_data["gross_profit"],
            "net_profit": current_data["net_profit"],
            "profit_margin": current_data["profit_margin"],
            "transaction_count": current_data["sales_count"],
            "week_over_week": {
                "revenue_change": round(revenue_change, 2),
                "expense_change": round(expense_change, 2),
                "profit_change": round(profit_change, 2),
            },
            "top_products": top_products,
            "expense_breakdown": expense_breakdown,
            "daily_breakdown": daily_breakdown,
        }

        return self.format_response(
            report_type="weekly_summary",
            data=report_data,
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            cached=False
        )

    def _get_gl_data(self, start_date: date, end_date: date, branch=None) -> dict:
        """Get financial data from G/L entries (same as P&L statement)"""
        gl_queryset = GeneralLedgerEntry.objects.filter(
            posting_date__range=[start_date, end_date]
        )
        if branch:
            gl_queryset = gl_queryset.filter(global_dimension_1=branch)

        # Revenue (multiply by -1 because income accounts are negative)
        revenue_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement",
            accountcategory="Income"
        )
        total_revenue = gl_queryset.filter(
            gl_account__in=revenue_accounts
        ).aggregate(amount=Sum(F("amount") * -1))["amount"] or 0

        # Cost of Goods Sold
        cogs_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement",
            accountcategory="Cost of Goods Sold"
        )
        total_cogs = gl_queryset.filter(
            gl_account__in=cogs_accounts
        ).aggregate(amount=Sum("amount"))["amount"] or 0

        # Operating Expenses
        expense_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement",
            accountcategory="Expense"
        )
        total_expenses = gl_queryset.filter(
            gl_account__in=expense_accounts
        ).aggregate(amount=Sum("amount"))["amount"] or 0

        # Get transaction counts
        sales_qs = SalesInvoice.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted"
        )
        if branch:
            sales_qs = sales_qs.filter(global_dimension_1=branch)
        sales_count = sales_qs.count()
        
        expense_qs = Expense.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted"
        )
        if branch:
            expense_qs = expense_qs.filter(global_dimension_1=branch)
        expense_count = expense_qs.count()

        # Calculate profits
        gross_profit = float(total_revenue) - float(total_cogs)
        net_profit = gross_profit - float(total_expenses)
        profit_margin = calculate_profit_margin(net_profit, total_revenue)

        return {
            "revenue": float(total_revenue),
            "cogs": float(total_cogs),
            "total_expenses": float(total_expenses),
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "profit_margin": round(profit_margin, 2),
            "sales_count": sales_count,
            "expense_count": expense_count,
        }

    def _get_top_products(self, start_date: date, end_date: date, limit: int = 5, branch=None) -> list:
        """Get top products by revenue for the week"""
        qs = SalesInvoiceLine.objects.filter(
            sales_invoice__posting_date__range=[start_date, end_date],
            sales_invoice__status="Posted"
        )
        if branch:
            qs = qs.filter(sales_invoice__global_dimension_1=branch)
        top_products = (
            qs
            .values("item__item_name", "item_id")
            .annotate(
                total_revenue=Sum(F("quantity") * F("unit_price"))
            )
            .order_by("-total_revenue")[:limit]
        )

        # Calculate total revenue for percentages
        total_revenue = sum(p["total_revenue"] for p in top_products if p["total_revenue"])

        result = []
        for product in top_products:
            revenue = float(product["total_revenue"] or 0)
            percentage = (revenue / float(total_revenue)) * 100 if total_revenue > 0 else 0
            
            result.append({
                "item_id": product["item_id"],
                "item_name": product["item__item_name"],
                "revenue": revenue,
                "percentage": round(percentage, 1),
            })

        return result

    def _get_expense_breakdown(self, start_date: date, end_date: date, branch=None) -> list:
        """Get expense breakdown by type"""
        from expenses.models import ExpenseType
        
        qs = Expense.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted"
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)
        expense_breakdown = (
            qs
            .values("expense_type__name", "expense_type_id")
            .annotate(
                total_amount=Sum("amount"),
                expense_count=Count("id")
            )
            .order_by("-total_amount")
        )

        # Calculate total for percentages
        total_expenses = sum(e["total_amount"] for e in expense_breakdown if e["total_amount"])

        result = []
        for expense in expense_breakdown:
            amount = float(expense["total_amount"] or 0)
            percentage = (amount / float(total_expenses)) * 100 if total_expenses > 0 else 0
            
            result.append({
                "expense_type_id": expense["expense_type_id"],
                "expense_type_name": expense["expense_type__name"],
                "total_amount": amount,
                "expense_count": expense["expense_count"],
                "percentage": round(percentage, 1),
            })

        return result

    def _get_daily_breakdown(self, start_date: date, end_date: date, branch=None) -> list:
        """Get day-by-day breakdown for the week"""
        result = []
        current_date = start_date

        while current_date <= end_date:
            daily_data = self._get_gl_data(current_date, current_date, branch=branch)
            
            result.append({
                "date": current_date.isoformat(),
                "day_name": current_date.strftime("%A"),
                "sales": daily_data["revenue"],
                "expenses": daily_data["total_expenses"],
                "profit": daily_data["net_profit"],
            })

            current_date += timedelta(days=1)

        return result
