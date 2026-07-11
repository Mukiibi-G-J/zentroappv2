"""
Product Profitability Report Service
Analyzes product profitability with revenue, cost, profit, and margin calculations.
"""

from datetime import date

from django.core.paginator import Paginator
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Cast

from sales.models import SalesInvoiceLine
from items.models import ValueEntry
from items.enums import EntryType as ItemEntryType, DocumentType as ItemDocumentType

from .base_report_service import BaseReportService
from ..utils.calculations import calculate_profit_margin


class ProductProfitabilityService(BaseReportService):
    """Service for generating product profitability reports"""

    CACHE_TTL = 900  # 15 minutes

    def generate_report(
        self,
        start_date: date,
        end_date: date,
        category: str = None,
        product_type: str = None,
        sort_by: str = "profit",
        page: int = 1,
        page_size: int = 50,
        branch=None,
    ) -> dict:
        """
        Generate product profitability report.

        Args:
            start_date: Start date
            end_date: End date
            category: Filter by product category (optional)
            product_type: Filter by product/service (optional)
            sort_by: Sort field (profit, margin, revenue, units)
            page: Page number for pagination
            page_size: Items per page

        Returns:
            Dictionary with report data
        """
        self.start_timer()

        # Build base query for posted invoice lines within range
        queryset = SalesInvoiceLine.objects.filter(
            sales_invoice__posting_date__range=[start_date, end_date],
            sales_invoice__status="Posted",
        )
        if branch:
            queryset = queryset.filter(sales_invoice__global_dimension_1=branch)

        # Apply filters
        if category:
            queryset = queryset.filter(item__category__description=category)

        if product_type:
            queryset = queryset.filter(line_type=product_type)

        product_list = []

        # Split into product and service lines
        product_lines = queryset.filter(line_type="product")
        service_lines = queryset.filter(line_type="service")

        money_field = DecimalField(max_digits=18, decimal_places=2)
        quantity_field = DecimalField(max_digits=18, decimal_places=4)

        # ------------------------------------------------------------------
        # Handle product lines (inventory items) using Value Entries for cost
        # ------------------------------------------------------------------
        if product_lines.exists():
            product_revenue_expression = ExpressionWrapper(
                F("quantity") * F("unit_price"),
                output_field=money_field,
            )

            product_line_aggs = list(
                product_lines.values("item_id", "item__item_name").annotate(
                    units_sold=Sum("quantity"),
                    total_revenue=Sum(
                        product_revenue_expression, output_field=money_field
                    ),
                    total_cost=Sum("total_cost"),
                )
            )

            product_line_map = {row["item_id"]: row for row in product_line_aggs}

            product_item_ids = list(product_line_map.keys())

            value_entries = ValueEntry.objects.filter(
                posting_date__range=[start_date, end_date],
                entry_type=ItemEntryType.DirectCost.value,
                document_type__in=[ItemDocumentType.Sales.value, "Credit Memo"],
                item_id__in=product_item_ids,
            )
            if branch:
                value_entries = value_entries.filter(global_dimension_1=branch)

            if category:
                value_entries = value_entries.filter(
                    item__category__description=category
                )

            value_data = {
                row["item_id"]: row
                for row in value_entries.values("item_id", "item__item_name").annotate(
                    total_revenue=Sum(Cast("sales_amount", money_field)),
                    total_cost=Sum(Cast("cost_amount", money_field)),
                    quantity_sum=Sum(
                        "item_ledger_entry_quantity", output_field=quantity_field
                    ),
                )
            }

            product_item_ids = set(product_item_ids) | set(value_data.keys())

            for item_id in product_item_ids:
                line_row = product_line_map.get(item_id)
                value_row = value_data.get(item_id)

                item_name = None
                if line_row:
                    item_name = line_row["item__item_name"]
                elif value_row:
                    item_name = value_row["item__item_name"]

                if not item_name:
                    # Should not happen, but guard clause
                    continue

                # Units sold: prefer value entry data to capture returns
                units_sold = 0.0
                if value_row and value_row.get("quantity_sum") is not None:
                    units_sold = float(-(value_row["quantity_sum"] or 0))
                elif line_row:
                    units_sold = float(line_row.get("units_sold") or 0)

                # Revenue
                revenue = 0.0
                if value_row and value_row.get("total_revenue") is not None:
                    revenue = float(value_row["total_revenue"] or 0)
                elif line_row:
                    revenue = float(line_row.get("total_revenue") or 0)

                # Cost
                cost = 0.0
                if value_row and value_row.get("total_cost") is not None:
                    cost = float(value_row["total_cost"] or 0)
                elif line_row:
                    cost = float(line_row.get("total_cost") or 0)

                profit = revenue - cost
                margin = calculate_profit_margin(profit, revenue)

                avg_unit_price = revenue / units_sold if units_sold else 0
                avg_unit_cost = cost / units_sold if units_sold else 0

                product_list.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "line_type": "product",
                        "units_sold": round(units_sold, 4),
                        "total_revenue": round(revenue, 2),
                        "total_cost": round(cost, 2),
                        "profit": round(profit, 2),
                        "profit_margin": round(margin, 2),
                        "avg_unit_price": round(avg_unit_price, 2),
                        "avg_unit_cost": round(avg_unit_cost, 2),
                    }
                )

        # ------------------------------------------------------------------
        # Handle service lines (non-inventory) using line cost data
        # ------------------------------------------------------------------
        if service_lines.exists() and (not product_type or product_type == "service"):
            service_revenue_expression = ExpressionWrapper(
                F("quantity") * F("unit_price"),
                output_field=money_field,
            )

            service_aggs = service_lines.values("item_id", "item__item_name").annotate(
                units_sold=Sum("quantity"),
                total_revenue=Sum(service_revenue_expression, output_field=money_field),
                total_cost=Sum("total_cost"),
            )

            for row in service_aggs:
                item_id = row["item_id"]
                item_name = row["item__item_name"]
                units_sold = float(row.get("units_sold") or 0)
                revenue = float(row.get("total_revenue") or 0)
                cost = float(row.get("total_cost") or 0)
                profit = revenue - cost
                margin = calculate_profit_margin(profit, revenue)
                avg_unit_price = revenue / units_sold if units_sold else 0
                avg_unit_cost = cost / units_sold if units_sold else 0

                product_list.append(
                    {
                        "item_id": item_id,
                        "item_name": item_name,
                        "line_type": "service",
                        "units_sold": round(units_sold, 4),
                        "total_revenue": round(revenue, 2),
                        "total_cost": round(cost, 2),
                        "profit": round(profit, 2),
                        "profit_margin": round(margin, 2),
                        "avg_unit_price": round(avg_unit_price, 2),
                        "avg_unit_cost": round(avg_unit_cost, 2),
                    }
                )

        # Sort products
        sort_fields = {
            "profit": lambda x: x["profit"],
            "margin": lambda x: x["profit_margin"],
            "revenue": lambda x: x["total_revenue"],
            "units": lambda x: x["units_sold"],
        }

        if sort_by in sort_fields:
            product_list.sort(key=sort_fields[sort_by], reverse=True)

        # Calculate summary statistics
        total_products = len(product_list)
        profitable_count = sum(1 for p in product_list if p["profit"] > 0)
        loss_making_count = sum(1 for p in product_list if p["profit"] < 0)
        avg_margin = (
            sum(p["profit_margin"] for p in product_list) / total_products
            if total_products > 0
            else 0
        )

        # Paginate results
        paginator = Paginator(product_list, page_size)
        page_obj = paginator.get_page(page)

        # Compile report data
        report_data = {
            "summary": {
                "total_products": total_products,
                "profitable_products": profitable_count,
                "loss_making_products": loss_making_count,
                "avg_profit_margin": round(avg_margin, 2),
            },
            "products": list(page_obj),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "total_items": total_products,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
            "filters": {
                "category": category,
                "product_type": product_type,
                "sort_by": sort_by,
            },
        }

        return self.format_response(
            report_type="product_profitability",
            data=report_data,
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            cached=False,
        )
