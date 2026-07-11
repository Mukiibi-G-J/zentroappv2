from dataclasses import dataclass
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import G_LAccount


@dataclass(frozen=True)
class LoanAccountDefinition:
    no: str
    name: str
    accounttype: str
    indentation: int
    income_balance: str
    accountcategory: str
    totaling: str | None = None
    direct_posting: bool = False

    @property
    def defaults(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "indentation": self.indentation,
            "income_balance": self.income_balance,
            "accountcategory": self.accountcategory,
            "debit_credit": "Both",
            "accounttype": self.accounttype,
            "totaling": self.totaling,
            "direct_posting": self.direct_posting,
            "blocked": False,
        }


LOAN_ACCOUNTS: Tuple[LoanAccountDefinition, ...] = (
    # Balance Sheet - Liabilities - Short-term Liabilities (5300-5995)
    # Placed after 5310 (Revolving Credit) and before 5350 (Sales Prepayments)
    LoanAccountDefinition(
        no="5320",
        name="Loan Payable – Short Term",
        accounttype="Posting",
        indentation=2,
        income_balance="Balance Sheet",
        accountcategory="Liabilities",
        direct_posting=True,
    ),
    # Income Statement - Operating Expenses (8000-8695)
    # Placed in Other Operating Expenses section (8600-8690)
    LoanAccountDefinition(
        no="8615",
        name="Interest Expense",
        accounttype="Posting",
        indentation=2,
        income_balance="Income Statement",
        accountcategory="Expense",
        direct_posting=True,
    ),
    LoanAccountDefinition(
        no="8616",
        name="Bank Charges / Loan Fees",
        accounttype="Posting",
        indentation=2,
        income_balance="Income Statement",
        accountcategory="Expense",
        direct_posting=True,
    ),
)


@transaction.atomic
def ensure_loan_accounts() -> Dict[str, int]:
    summary = {"created": 0, "updated": 0, "skipped": 0}

    for definition in LOAN_ACCOUNTS:
        account, created = G_LAccount.objects.get_or_create(
            no=definition.no,
            defaults=definition.defaults,
        )

        if created:
            summary["created"] += 1
            continue

        # Check if account exists but might have different settings
        # For loan-specific accounts (5320, 8615, 8616), update all fields
        if definition.no in ["5320", "8615", "8616"]:
            # For loan-specific accounts, update all fields
            changed_fields: List[str] = []
            for field_name, value in definition.defaults.items():
                if getattr(account, field_name) != value:
                    setattr(account, field_name, value)
                    changed_fields.append(field_name)

            if changed_fields:
                account.save(update_fields=changed_fields)
                summary["updated"] += 1
            else:
                summary["skipped"] += 1

    return summary


class Command(BaseCommand):
    help = "Ensure loan-related GL accounts exist (Loan Payable Short Term, Interest Expense, Bank Charges)"

    def handle(self, *args, **options):
        summary = ensure_loan_accounts()

        message = (
            "Loan accounts ready: "
            f"created: {summary['created']}, "
            f"updated: {summary['updated']}, "
            f"skipped: {summary['skipped']}"
        )
        self.stdout.write(self.style.SUCCESS(message))
