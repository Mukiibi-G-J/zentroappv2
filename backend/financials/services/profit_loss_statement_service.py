from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Callable, Dict, List, Optional

from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from financials.models import G_LAccount, GeneralLedgerEntry
from financials.currency import get_local_currency_code
from reports.utils.formatters import format_currency


@dataclass
class PLAccountRow:
    no: str
    name: str
    indentation: int
    account_type: Optional[str]
    account_category: Optional[str]
    balance: float


class ProfitLossStatementService:
    """
    Profit & Loss (Income Statement) for a date range, aligned with the web UI logic.
    Uses the same G/L entry queryset pattern as BalanceSheetService (e.g. branch filter).
    """

    def __init__(self, queryset=None):
        self.base_queryset = queryset or GeneralLedgerEntry.objects.all()

    def _rows_for_period(self, start_date, end_date) -> List[PLAccountRow]:
        gl_q = self.base_queryset.filter(
            posting_date__gte=start_date,
            posting_date__lte=end_date,
        )
        aggregated = (
            gl_q.filter(gl_account__income_balance="Income Statement")
            .values("gl_account__no")
            .annotate(balance=Sum("amount"))
        )
        balance_by_no: Dict[str, float] = {
            row["gl_account__no"]: float(row["balance"] or 0) for row in aggregated
        }

        chart = G_LAccount.objects.filter(
            income_balance="Income Statement",
        ).order_by("indentation", "no")

        rows: List[PLAccountRow] = []
        for acct in chart:
            rows.append(
                PLAccountRow(
                    no=acct.no,
                    name=acct.name,
                    indentation=acct.indentation or 0,
                    account_type=acct.accounttype,
                    account_category=acct.accountcategory,
                    balance=balance_by_no.get(acct.no, 0.0),
                )
            )
        return rows

    @staticmethod
    def _filter_visible(rows: List[PLAccountRow], category: str) -> List[PLAccountRow]:
        return [
            r
            for r in rows
            if r.account_category == category
            and (r.account_type != "Posting" or r.balance != 0)
        ]

    def generate(self, start_date, end_date) -> dict:
        rows = self._rows_for_period(start_date, end_date)

        revenue_rows = self._filter_visible(rows, "Income")
        cogs_rows = self._filter_visible(rows, "Cost of Goods Sold")
        expense_rows = self._filter_visible(rows, "Expense")

        revenue_total_raw = sum(r.balance for r in revenue_rows)
        revenue_total = revenue_total_raw * -1
        cogs_total = sum(r.balance for r in cogs_rows)
        expenses_total = sum(r.balance for r in expense_rows)
        gross_profit = revenue_total - cogs_total
        net_profit = gross_profit - expenses_total

        def rows_to_dicts(sub: List[PLAccountRow]):
            return [
                {
                    "no": r.no,
                    "name": r.name,
                    "indentation": r.indentation,
                    "accountType": r.account_type,
                    "balance": round(r.balance, 2),
                }
                for r in sub
            ]

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "revenue": {
                "total": round(revenue_total, 2),
                "accounts": rows_to_dicts(revenue_rows),
            },
            "cost_of_goods_sold": {
                "total": round(cogs_total, 2),
                "accounts": rows_to_dicts(cogs_rows),
            },
            "expenses": {
                "total": round(expenses_total, 2),
                "accounts": rows_to_dicts(expense_rows),
            },
            "gross_profit": round(gross_profit, 2),
            "net_profit": round(net_profit, 2),
        }

    def generate_pdf(self, start_date, end_date) -> bytes:
        data = self.generate(start_date, end_date)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            leftMargin=40,
            rightMargin=40,
            topMargin=50,
            bottomMargin=40,
        )
        styles = getSampleStyleSheet()
        elements = []

        sd = datetime.strptime(data["start_date"], "%Y-%m-%d").strftime("%b %d, %Y")
        ed = datetime.strptime(data["end_date"], "%Y-%m-%d").strftime("%b %d, %Y")

        elements.append(Paragraph("Profit &amp; Loss Statement", styles["Title"]))
        elements.append(
            Paragraph(
                f"For the period {sd} &ndash; {ed}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 18))

        summary_data = [
            ["Total Revenue", self._format_currency(abs(data["revenue"]["total"]))],
            [
                "Cost of Goods Sold",
                self._format_currency(data["cost_of_goods_sold"]["total"]),
            ],
            ["Gross Profit", self._format_currency(data["gross_profit"])],
            ["Operating Expenses", self._format_currency(data["expenses"]["total"])],
            ["Net Profit / Loss", self._format_currency(data["net_profit"])],
        ]
        summary_table = Table(summary_data, colWidths=[250, 200])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 18))

        elements.extend(
            self._build_section_table(
                "Revenue",
                data["revenue"]["accounts"],
                lambda b: abs(b),
                styles,
            )
        )
        elements.append(Spacer(1, 12))
        elements.extend(
            self._build_section_table(
                "Cost of Goods Sold",
                data["cost_of_goods_sold"]["accounts"],
                lambda b: b,
                styles,
            )
        )
        elements.append(Spacer(1, 12))
        elements.extend(
            self._build_section_table(
                "Operating Expenses",
                data["expenses"]["accounts"],
                lambda b: b,
                styles,
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.read()

    def _build_section_table(
        self,
        title: str,
        accounts: List[dict],
        amount_fn: Callable[[float], float],
        styles,
    ):
        heading = Paragraph(title, styles["Heading3"])
        if not accounts:
            return [heading, Paragraph("No data in this section", styles["Normal"])]

        table_data = [["Account", f"Amount ({get_local_currency_code()})"]]
        for account in accounts:
            label = self._format_account_label(account)
            bal = float(account.get("balance") or 0)
            if account.get("accountType") == "Begin-Total" and bal == 0:
                table_data.append([label, ""])
            else:
                table_data.append([label, self._format_currency(amount_fn(bal))])

        table = Table(table_data, colWidths=[330, 140])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fb")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ]
            )
        )
        return [heading, table]

    @staticmethod
    def _format_currency(value: float) -> str:
        return format_currency(value)

    @staticmethod
    def _format_account_label(account: dict) -> str:
        indentation = account.get("indentation", 0) or 0
        prefix = " " * (indentation * 4)
        return f"{prefix}{account['name']}"
