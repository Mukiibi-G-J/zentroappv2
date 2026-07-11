"""
Daily Profit Report Service
Generates daily profit report using G/L entries (same as P&L statement).
"""

from datetime import date, timedelta
from django.db.models import Sum, F
from decimal import Decimal

from financials.models import GeneralLedgerEntry, G_LAccount
from .base_report_service import BaseReportService
from ..utils.calculations import calculate_growth_percentage, calculate_profit_margin


class DailyProfitService(BaseReportService):
    """Service for generating daily profit reports using G/L entries"""

    CACHE_TTL = 300  # 5 minutes

    def generate_report(self, report_date: date, branch=None) -> dict:
        """
        Generate daily profit report for a specific date using G/L entries.

        Args:
            report_date: Date to generate report for
            branch: Optional DimensionValue to filter by branch

        Returns:
            Dictionary with report data
        """
        self.start_timer()

        # Get current day data from G/L
        current_data = self._get_gl_data(report_date, report_date, branch=branch)

        # Get previous day data for comparison
        previous_date = report_date - timedelta(days=1)
        previous_data = self._get_gl_data(previous_date, previous_date, branch=branch)

        # Calculate day-over-day changes
        change_amount = current_data["net_profit"] - previous_data["net_profit"]
        change_percentage = calculate_growth_percentage(
            current_data["net_profit"], previous_data["net_profit"]
        )

        # Compile report data
        report_data = {
            "report_date": report_date.isoformat(),
            "total_sales": current_data["revenue"],
            "sales_count": current_data["sales_count"],
            "avg_transaction": current_data["avg_transaction"],
            "total_expenses": current_data["total_expenses"],
            "expense_count": current_data["expense_count"],
            "total_cogs": current_data["cogs"],
            "gross_profit": current_data["gross_profit"],
            "net_profit": current_data["net_profit"],
            "profit_margin": current_data["profit_margin"],
            "comparison": {
                "previous_day_date": previous_date.isoformat(),
                "previous_day_profit": previous_data["net_profit"],
                "change_amount": change_amount,
                "change_percentage": round(change_percentage, 2),
            },
        }

        return self.format_response(
            report_type="daily_profit",
            data=report_data,
            period={"date": report_date.isoformat()},
            cached=False,
        )

    def _get_gl_data(self, start_date: date, end_date: date, branch=None) -> dict:
        """
        Get financial data from General Ledger entries (same as P&L statement).

        Args:
            start_date: Start date
            end_date: End date
            branch: Optional DimensionValue to filter by branch

        Returns:
            Dictionary with revenue, cogs, expenses, and profit calculations
        """
        # Query G/L entries for the period
        gl_queryset = GeneralLedgerEntry.objects.filter(
            posting_date__range=[start_date, end_date]
        )
        if branch:
            gl_queryset = gl_queryset.filter(global_dimension_1=branch)

        # Revenue (Income accounts) - multiply by -1 because income accounts are negative
        revenue_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement", accountcategory="Income"
        )
        total_revenue = (
            gl_queryset.filter(gl_account__in=revenue_accounts).aggregate(
                amount=Sum(F("amount") * -1)
            )["amount"]
            or 0
        )

        # Cost of Goods Sold
        cogs_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement", accountcategory="Cost of Goods Sold"
        )
        total_cogs = (
            gl_queryset.filter(gl_account__in=cogs_accounts).aggregate(
                amount=Sum("amount")
            )["amount"]
            or 0
        )

        # Operating Expenses
        expense_accounts = G_LAccount.objects.filter(
            income_balance="Income Statement", accountcategory="Expense"
        )
        total_expenses = (
            gl_queryset.filter(gl_account__in=expense_accounts).aggregate(
                amount=Sum("amount")
            )["amount"]
            or 0
        )

        # Get transaction counts from source documents
        from sales.models import SalesInvoice
        from expenses.models import Expense

        sales_qs = SalesInvoice.objects.filter(
            posting_date__range=[start_date, end_date], status="Posted"
        )
        if branch:
            sales_qs = sales_qs.filter(global_dimension_1=branch)
        sales_count = sales_qs.count()

        expense_qs = Expense.objects.filter(
            posting_date__range=[start_date, end_date], status="Posted"
        )
        if branch:
            expense_qs = expense_qs.filter(global_dimension_1=branch)
        expense_count = expense_qs.count()

        # Calculate profits
        gross_profit = float(total_revenue) - float(total_cogs)
        net_profit = gross_profit - float(total_expenses)
        profit_margin = calculate_profit_margin(net_profit, total_revenue)
        avg_transaction = float(total_revenue) / sales_count if sales_count > 0 else 0

        return {
            "revenue": float(total_revenue),
            "cogs": float(total_cogs),
            "total_expenses": float(total_expenses),
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "profit_margin": round(profit_margin, 2),
            "sales_count": sales_count,
            "expense_count": expense_count,
            "avg_transaction": avg_transaction,
        }
