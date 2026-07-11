from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import List, Optional

from django.db.models import Sum
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from financials.models import GeneralLedgerEntry
from financials.currency import get_local_currency_code
from reports.utils.formatters import format_currency


@dataclass
class BalanceSheetAccount:
    no: str
    name: str
    indentation: int
    account_type: Optional[str]
    balance: float


@dataclass
class BalanceSheetSection:
    accounts: List[BalanceSheetAccount]
    total: float


class BalanceSheetService:
    """
    Encapsulates Balance Sheet aggregations so multiple views can reuse the logic.
    """

    def __init__(self, queryset=None):
        self.base_queryset = queryset or GeneralLedgerEntry.objects.all()

    def generate(self, as_of_date: Optional[date] = None) -> dict:
        """
        Build the balance sheet snapshot for a given date.
        """
        as_of = as_of_date or timezone.now().date()
        gl_queryset = self.base_queryset.filter(posting_date__lte=as_of)

        assets = self._build_section(gl_queryset, category="Assets")
        liabilities = self._build_section(gl_queryset, category="Liabilities")
        equity = self._build_section(gl_queryset, category="Equity")

        # Automatically roll current period profit/loss into Equity so that
        # Assets always equal Liabilities + Equity from a reporting perspective.
        current_profit = self._calculate_current_profit(gl_queryset)
        if current_profit:
            equity.accounts.append(
                BalanceSheetAccount(
                    no="CURRENT_PROFIT",
                    name="Current Period Profit/Loss",
                    indentation=0,
                    account_type=None,
                    balance=current_profit,
                )
            )
            equity.total += current_profit

        liabilities_plus_equity = liabilities.total + equity.total
        balance_check = {
            "assets": round(assets.total, 2),
            "liabilities_plus_equity": round(liabilities_plus_equity, 2),
            "difference": round(assets.total - liabilities_plus_equity, 2),
        }

        return {
            "as_of_date": as_of.isoformat(),
            "assets": self._section_to_dict(assets),
            "liabilities": self._section_to_dict(liabilities),
            "equity": self._section_to_dict(equity),
            "balance_check": balance_check,
        }

    def generate_pdf(self, as_of_date: Optional[date] = None) -> bytes:
        """
        Generate a PDF representation of the balance sheet snapshot.
        """
        data = self.generate(as_of_date)
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

        display_date = data.get("as_of_date")
        if display_date:
            display_date = datetime.strptime(display_date, "%Y-%m-%d").strftime(
                "%b %d, %Y"
            )

        elements.append(Paragraph("Balance Sheet", styles["Title"]))
        elements.append(
            Paragraph(
                f"As of {display_date or timezone.now().date().strftime('%b %d, %Y')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 18))

        summary_data = [
            ["Total Assets", self._format_currency(data["assets"]["total"])],
            ["Total Liabilities", self._format_currency(data["liabilities"]["total"])],
            ["Total Equity", self._format_currency(data["equity"]["total"])],
            [
                "Liabilities + Equity",
                self._format_currency(data["balance_check"]["liabilities_plus_equity"]),
            ],
            [
                "Balance Difference",
                self._format_currency(data["balance_check"]["difference"]),
            ],
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
            self._build_account_table("Assets", data["assets"]["accounts"], styles)
        )
        elements.append(Spacer(1, 12))
        elements.extend(
            self._build_account_table(
                "Liabilities", data["liabilities"]["accounts"], styles
            )
        )
        elements.append(Spacer(1, 12))
        elements.extend(
            self._build_account_table("Equity", data["equity"]["accounts"], styles)
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.read()

    def _build_section(self, queryset, category: str) -> BalanceSheetSection:
        multiplier = self._get_multiplier(category)
        accounts = (
            queryset.filter(
                gl_account__income_balance="Balance Sheet",
                gl_account__accountcategory=category,
            )
            .values(
                "gl_account__no",
                "gl_account__name",
                "gl_account__indentation",
                "gl_account__accounttype",
            )
            .annotate(balance=Sum("amount"))
            .order_by("gl_account__indentation", "gl_account__no")
        )

        normalized_accounts: List[BalanceSheetAccount] = [
            BalanceSheetAccount(
                no=item["gl_account__no"],
                name=item["gl_account__name"],
                indentation=item["gl_account__indentation"] or 0,
                account_type=item["gl_account__accounttype"],
                balance=float(item["balance"] or 0) * multiplier,
            )
            for item in accounts
        ]

        total_balance = sum(account.balance for account in normalized_accounts)

        return BalanceSheetSection(accounts=normalized_accounts, total=total_balance)

    @staticmethod
    def _get_multiplier(category: str) -> int:
        """
        Assets should stay positive, while liabilities and equity should show as positive
        even though their GL balances are normally negative (credit). Apply -1 for those
        categories so presentation matches business expectations.
        """
        if category in {"Liabilities", "Equity"}:
            return -1
        return 1

    @staticmethod
    def _calculate_current_profit(queryset) -> float:
        """
        Calculate current period profit or loss from Income Statement accounts.

        In the general ledger, income (credit) balances are typically negative.
        To present profit as a positive number on the balance sheet, we invert
        the sign of the aggregated Income Statement balance.
        """
        from django.db.models import Sum

        raw_total = (
            queryset.filter(gl_account__income_balance="Income Statement").aggregate(
                total=Sum("amount")
            )["total"]
            or 0.0
        )
        return -float(raw_total)

    def _section_to_dict(self, section: BalanceSheetSection) -> dict:
        return {
            "total": round(section.total, 2),
            "accounts": [
                {
                    "no": account.no,
                    "name": account.name,
                    "indentation": account.indentation,
                    "accountType": account.account_type,
                    "balance": round(account.balance, 2),
                }
                for account in section.accounts
            ],
        }

    def _build_account_table(self, title: str, accounts: List[dict], styles):
        heading = Paragraph(title, styles["Heading3"])
        if not accounts:
            return [heading, Paragraph("No data available", styles["Normal"])]

        table_data = [["Account", f"Amount ({get_local_currency_code()})"]]
        for account in accounts:
            label = self._format_account_label(account)
            table_data.append([label, self._format_currency(account["balance"])])

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

