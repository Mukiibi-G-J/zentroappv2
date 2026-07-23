"""
Ensure Sales Line Discount G/L account and General Posting Setup assignment.

Invoice posting with a line (or invoice) discount requires
GeneralPostingSetup.sales_line_discount_account for the
business + product posting group pair (e.g. DOMESTIC / RETAIL).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import G_LAccount
from postings.models import (
    GeneralBusinessPostingGroup,
    GeneralPostingSetup,
    GeneralProductPostingGroup,
)


@dataclass(frozen=True)
class DiscountAccountDefinition:
    no: str
    name: str
    accounttype: str
    indentation: int
    totaling: str | None = None
    direct_posting: bool = True

    @property
    def defaults(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "indentation": self.indentation,
            "income_balance": "Income Statement",
            "accountcategory": "Income",
            "debit_credit": "Both",
            "accounttype": self.accounttype,
            "totaling": self.totaling,
            "direct_posting": self.direct_posting,
            "blocked": False,
        }


# Matches tenant_semuna_export CoA (account 6910 "Discount Granted").
DISCOUNT_ACCOUNT = DiscountAccountDefinition(
    no="6910",
    name="Discount Granted",
    accounttype="Posting",
    indentation=1,
    direct_posting=True,
)


@transaction.atomic
def ensure_discount_granted_account(
    account_no: str = DISCOUNT_ACCOUNT.no,
) -> Dict[str, int]:
    summary = {"created": 0, "updated": 0}
    definition = DISCOUNT_ACCOUNT
    if account_no != definition.no:
        # Allow override of number while keeping the same metadata shape.
        definition = DiscountAccountDefinition(
            no=account_no,
            name=DISCOUNT_ACCOUNT.name,
            accounttype=DISCOUNT_ACCOUNT.accounttype,
            indentation=DISCOUNT_ACCOUNT.indentation,
            totaling=DISCOUNT_ACCOUNT.totaling,
            direct_posting=DISCOUNT_ACCOUNT.direct_posting,
        )

    account, created = G_LAccount.objects.get_or_create(
        no=definition.no,
        defaults=definition.defaults,
    )
    if created:
        summary["created"] += 1
        return summary

    changed_fields: List[str] = []
    for field_name, value in definition.defaults.items():
        if getattr(account, field_name) != value:
            setattr(account, field_name, value)
            changed_fields.append(field_name)
    if changed_fields:
        account.save(update_fields=changed_fields)
        summary["updated"] += 1
    return summary


@transaction.atomic
def assign_sales_line_discount_account(account_no: str = DISCOUNT_ACCOUNT.no) -> int:
    try:
        discount_account = G_LAccount.objects.get(no=account_no)
    except G_LAccount.DoesNotExist:
        return 0

    updated = 0
    for setup in GeneralPostingSetup.objects.filter(
        sales_line_discount_account__isnull=True
    ):
        setup.sales_line_discount_account = discount_account
        setup.save(update_fields=["sales_line_discount_account"])
        updated += 1
    return updated


_SETUP_COPY_FIELDS = (
    "sales_account",
    "purchase_account",
    "cogs_account",
    "inventory_adjustment_account",
    "direct_cost_applied_account",
    "prepayment_account",
)


@transaction.atomic
def ensure_discount_posting_setup_pair(
    business_code: str = "DOMESTIC",
    product_code: str = "RETAIL",
    account_no: str = DISCOUNT_ACCOUNT.no,
) -> dict:
    """
    Ensure DOMESTIC / RETAIL (or override) General Posting Setup has
    sales_line_discount_account set. Creates the pair row if missing.
    """
    result = {"pair_rows_updated": 0, "pair_row_created": False}

    try:
        discount_account = G_LAccount.objects.get(no=account_no)
    except G_LAccount.DoesNotExist:
        return result

    gb, _ = GeneralBusinessPostingGroup.objects.get_or_create(
        code=business_code,
        defaults={"description": business_code},
    )
    gp, _ = GeneralProductPostingGroup.objects.get_or_create(
        code=product_code,
        defaults={"description": product_code},
    )

    qs = GeneralPostingSetup.objects.filter(
        general_business_posting_group=gb,
        general_product_posting_group=gp,
    )

    for setup in qs:
        if setup.sales_line_discount_account_id is None:
            setup.sales_line_discount_account = discount_account
            setup.save(update_fields=["sales_line_discount_account"])
            result["pair_rows_updated"] += 1

    if qs.filter(sales_line_discount_account__isnull=False).exists():
        return result

    if qs.exists():
        return result

    template = GeneralPostingSetup.objects.filter(
        general_product_posting_group=gp,
        general_business_posting_group__isnull=True,
    ).first()
    if template is None:
        template = GeneralPostingSetup.objects.filter(
            general_product_posting_group=gp
        ).first()

    create_kwargs = {
        "general_business_posting_group": gb,
        "general_product_posting_group": gp,
        "sales_line_discount_account": discount_account,
    }
    if template is not None:
        for field in _SETUP_COPY_FIELDS:
            create_kwargs[field] = getattr(template, field)

    GeneralPostingSetup.objects.create(**create_kwargs)
    result["pair_row_created"] = True
    return result


class Command(BaseCommand):
    help = (
        "Ensure G/L account 6910 (Discount Granted) exists, assign it as "
        "sales_line_discount_account on General Posting Setup rows (including "
        "DOMESTIC/RETAIL), and create the pair row when missing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-no",
            dest="account_no",
            default=DISCOUNT_ACCOUNT.no,
            help="G/L account number for sales line discounts (default: 6910).",
        )
        parser.add_argument(
            "--business-code",
            dest="business_code",
            default="DOMESTIC",
            help="General Business Posting Group code for the required setup pair.",
        )
        parser.add_argument(
            "--product-code",
            dest="product_code",
            default="RETAIL",
            help="General Product Posting Group code for the required setup pair.",
        )
        parser.add_argument(
            "--no-ensure-pair",
            action="store_true",
            help="Skip creating/updating the business+product General Posting Setup row.",
        )

    def handle(self, *args, **options):
        account_no = options["account_no"]
        summary = ensure_discount_granted_account(account_no)
        pair_info: dict = {}
        if not options["no_ensure_pair"]:
            pair_info = ensure_discount_posting_setup_pair(
                business_code=options["business_code"],
                product_code=options["product_code"],
                account_no=account_no,
            )
        assigned = assign_sales_line_discount_account(account_no)

        self.stdout.write(
            self.style.SUCCESS(
                "Discount Granted account ready "
                f"(created: {summary['created']}, updated: {summary['updated']}); "
                f"{assigned} General Posting Setup record(s) linked "
                "(null sales_line_discount_account filled)."
            )
        )
        if options["no_ensure_pair"]:
            return

        pair_label = f"{options['business_code']} / {options['product_code']}"
        if pair_info.get("pair_row_created"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created General Posting Setup {pair_label} "
                    f"with sales line discount account {account_no}."
                )
            )
        elif pair_info.get("pair_rows_updated", 0) > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Set sales_line_discount_account on "
                    f"{pair_info['pair_rows_updated']} {pair_label} setup row(s)."
                )
            )
        else:
            self.stdout.write(
                f"{pair_label} posting setup already has sales_line_discount_account."
            )
