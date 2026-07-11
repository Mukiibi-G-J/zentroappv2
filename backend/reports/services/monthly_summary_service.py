"""
Monthly Summary Report Service
Generates comprehensive monthly business overview using G/L entries.
"""
from datetime import date, timedelta
from django.db.models import Sum, Count, F
from decimal import Decimal
from calendar import monthrange

from financials.models import GeneralLedgerEntry, G_LAccount
from sales.models import SalesInvoice, SalesInvoiceLine
from expenses.models import Expense
from .base_report_service import BaseReportService
from ..utils.calculations import calculate_growth_percentage, calculate_profit_margin, calculate_average


class MonthlySummaryService(BaseReportService):
    """Service for generating monthly summary reports using G/L entries"""

    CACHE_TTL = 3600  # 1 hour

    def generate_report(self, month_str: str, branch=None) -> dict:
        """
        Generate monthly summary report using G/L entries.
        
        Args:
            month_str: Month in YYYY-MM format
            branch: Optional DimensionValue to filter by branch
        
        Returns:
            Dictionary with report data
        """
        self.start_timer()

        # Parse month and calculate date range
        year, month = map(int, month_str.split("-"))
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        # Get current month data from G/L
        current_data = self._get_gl_data(start_date, end_date, branch=branch)

        # Get previous month data for MoM comparison
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        
        prev_start = date(prev_year, prev_month, 1)
        _, prev_last_day = monthrange(prev_year, prev_month)
        prev_end = date(prev_year, prev_month, prev_last_day)
        
        previous_data = self._get_gl_data(prev_start, prev_end, branch=branch)

        # Calculate MoM changes
        revenue_change_mom = calculate_growth_percentage(
            current_data["revenue"], previous_data["revenue"]
        )
        expense_change_mom = calculate_growth_percentage(
            current_data["total_expenses"], previous_data["total_expenses"]
        )
        profit_change_mom = calculate_growth_percentage(
            current_data["net_profit"], previous_data["net_profit"]
        )

        # Get year-to-date (YTD) data
        ytd_start = date(year, 1, 1)
        ytd_data = self._get_gl_data(ytd_start, end_date, branch=branch)

        # Calculate KPIs
        days_in_month = (end_date - start_date).days + 1
        avg_daily_sales = calculate_average(current_data["revenue"], days_in_month)
        burn_rate = calculate_average(current_data["total_expenses"], days_in_month)

        # Get top 10 products
        top_products = self._get_top_products(start_date, end_date, limit=10, branch=branch)

        # Get top 10 customers
        top_customers = self._get_top_customers(start_date, end_date, limit=10, branch=branch)

        # Get 30-day daily trend
        daily_trends = self._get_daily_trends(start_date, end_date, branch=branch)

        # Compile report data
        report_data = {
            "financial_overview": {
                "total_revenue": current_data["revenue"],
                "total_expenses": current_data["total_expenses"],
                "net_profit": current_data["net_profit"],
                "profit_margin": current_data["profit_margin"],
            },
            "month_over_month": {
                "revenue_change": round(revenue_change_mom, 2),
                "expense_change": round(expense_change_mom, 2),
                "profit_change": round(profit_change_mom, 2),
            },
            "year_to_date": {
                "total_revenue": ytd_data["revenue"],
                "total_expenses": ytd_data["total_expenses"],
                "net_profit": ytd_data["net_profit"],
            },
            "kpis": {
                "avg_daily_sales": round(avg_daily_sales, 2),
                "burn_rate": round(burn_rate, 2),
                "avg_profit_margin": current_data["profit_margin"],
                "days_in_month": days_in_month,
                "total_transactions": current_data["sales_count"],
            },
            "top_products": top_products,
            "top_customers": top_customers,
            "daily_trends": daily_trends,
        }

        return self.format_response(
            report_type="monthly_summary",
            data=report_data,
            period={
                "month": month_str,
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
        }

    def _get_top_products(self, start_date: date, end_date: date, limit: int = 10, branch=None) -> list:
        """Get top products by revenue"""
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
                total_revenue=Sum(F("quantity") * F("unit_price")),
                units_sold=Sum("quantity")
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
                "units_sold": product["units_sold"] or 0,
                "percentage": round(percentage, 1),
            })

        return result

    def _get_top_customers(self, start_date: date, end_date: date, limit: int = 10, branch=None) -> list:
        """Get top customers by total purchases"""
        qs = SalesInvoice.objects.filter(
            posting_date__range=[start_date, end_date],
            status="Posted"
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)
        # Calculate total from invoice lines for each customer
        top_customers = (
            qs
            .values("customer__name", "customer_id")
            .annotate(
                total_purchases=Sum(F("lines__quantity") * F("lines__unit_price")),
                transaction_count=Count("id")
            )
            .order_by("-total_purchases")[:limit]
        )

        # Calculate total for percentages
        total_purchases = sum(c["total_purchases"] for c in top_customers if c["total_purchases"])

        result = []
        for customer in top_customers:
            purchases = float(customer["total_purchases"] or 0)
            percentage = (purchases / float(total_purchases)) * 100 if total_purchases > 0 else 0
            
            result.append({
                "customer_id": customer["customer_id"],
                "customer_name": customer["customer__name"],
                "total_purchases": purchases,
                "transaction_count": customer["transaction_count"],
                "percentage": round(percentage, 1),
            })

        return result

    def _get_daily_trends(self, start_date: date, end_date: date, branch=None) -> list:
        """Get daily breakdown for the entire month"""
        result = []
        current_date = start_date

        while current_date <= end_date:
            daily_data = self._get_gl_data(current_date, current_date, branch=branch)

            result.append({
                "date": current_date.isoformat(),
                "day": current_date.day,
                "sales": daily_data["revenue"],
                "expenses": daily_data["total_expenses"],
                "profit": daily_data["net_profit"],
            })

            current_date += timedelta(days=1)

        return result
