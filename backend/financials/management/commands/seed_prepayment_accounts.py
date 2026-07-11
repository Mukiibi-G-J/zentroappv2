from dataclasses import dataclass
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import G_LAccount
from postings.models import (
    GeneralBusinessPostingGroup,
    GeneralPostingSetup,
    GeneralProductPostingGroup,
)


@dataclass(frozen=True)
class PrepaymentAccountDefinition:
    no: str
    name: str
    accounttype: str
    indentation: int
    totaling: str | None = None
    direct_posting: bool = False

    @property
    def defaults(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "indentation": self.indentation,
            "income_balance": "Balance Sheet",
            "accountcategory": "Liabilities",
            "debit_credit": "Both",
            "accounttype": self.accounttype,
            "totaling": self.totaling,
            "direct_posting": self.direct_posting,
            "blocked": False,
        }


PREPAYMENT_ACCOUNTS: Tuple[PrepaymentAccountDefinition, ...] = (
    PrepaymentAccountDefinition(
        no="5350",
        name="Sales Prepayments",
        accounttype="Begin-Total",
        indentation=2,
    ),
    PrepaymentAccountDefinition(
        no="5360",
        name="Customer Prepayments VAT 0%",
        accounttype="Posting",
        indentation=3,
    ),
    PrepaymentAccountDefinition(
        no="5390",
        name="Sales Prepayments, Total",
        accounttype="End-Total",
        indentation=2,
        totaling="5350..5389",
    ),
)


@transaction.atomic
def ensure_prepayment_accounts() -> Dict[str, int]:
    summary = {"created": 0, "updated": 0}

    for definition in PREPAYMENT_ACCOUNTS:
        account, created = G_LAccount.objects.get_or_create(
            no=definition.no,
            defaults=definition.defaults,
        )

        if created:
            summary["created"] += 1
            continue

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
def assign_default_prepayment_account(account_no: str = "5360") -> int:
    try:
        prepayment_account = G_LAccount.objects.get(no=account_no)
    except G_LAccount.DoesNotExist:
        return 0

    updated = 0

    for setup in GeneralPostingSetup.objects.filter(prepayment_account__isnull=True):
        setup.prepayment_account = prepayment_account
        setup.save(update_fields=["prepayment_account"])
        updated += 1

    return updated


_SETUP_COPY_FIELDS = (
    "sales_account",
    "purchase_account",
    "cogs_account",
    "inventory_adjustment_account",
    "direct_cost_applied_account",
    "sales_line_discount_account",
)


@transaction.atomic
def ensure_prepayment_posting_setup_pair(
    business_code: str = "DOMESTIC",
    product_code: str = "RETAIL",
    account_no: str = "5360",
) -> dict:
    """
    Prepayment line posting matches GeneralPostingSetup on BOTH
    general_business_posting_group and general_product_posting_group with
    prepayment_account set (see Preayment._prepare_line_context).

    Tenants that only have a product-group row (business NULL) still fail with
    "Prepayment account is not configured for DOMESTIC / RETAIL." — this creates
    or fixes the combined row (same pattern as tenant_semuna_export JSON id 1).
    """
    result = {"pair_rows_updated": 0, "pair_row_created": False}

    try:
        prepayment_account = G_LAccount.objects.get(no=account_no)
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
        if setup.prepayment_account_id is None:
            setup.prepayment_account = prepayment_account
            setup.save(update_fields=["prepayment_account"])
            result["pair_rows_updated"] += 1

    if qs.filter(prepayment_account__isnull=False).exists():
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
        "prepayment_account": prepayment_account,
    }
    if template is not None:
        for field in _SETUP_COPY_FIELDS:
            create_kwargs[field] = getattr(template, field)

    GeneralPostingSetup.objects.create(**create_kwargs)
    result["pair_row_created"] = True
    return result


class Command(BaseCommand):
    help = (
        "Ensure Sales Prepayment G/L accounts (5350–5390), a General Posting Setup "
        "row for business+product (default DOMESTIC+RETAIL) with prepayment_account, "
        "and backfill prepayment_account on any setup rows still NULL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-no",
            dest="account_no",
            default="5360",
            help="Override the default prepayment posting account number.",
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
        summary = ensure_prepayment_accounts()
        pair_info = {}
        if not options["no_ensure_pair"]:
            pair_info = ensure_prepayment_posting_setup_pair(
                business_code=options["business_code"],
                product_code=options["product_code"],
                account_no=options["account_no"],
            )
        assigned = assign_default_prepayment_account(options["account_no"])

        message = (
            "Prepayment accounts ready "
            f"(created: {summary['created']}, updated: {summary['updated']}); "
            f"{assigned} General Posting Setup records linked (null prepayment filled)."
        )
        self.stdout.write(self.style.SUCCESS(message))
        if not options["no_ensure_pair"]:
            if pair_info.get("pair_row_created"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created General Posting Setup "
                        f"{options['business_code']} / {options['product_code']} "
                        f"with prepayment account {options['account_no']} "
                        f"(copied from product template if available)."
                    )
                )
            elif pair_info.get("pair_rows_updated", 0) > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Set prepayment account on "
                        f"{pair_info['pair_rows_updated']} "
                        f"{options['business_code']} / {options['product_code']} "
                        f"setup row(s)."
                    )
                )
            else:
                self.stdout.write(
                    f"{options['business_code']} / {options['product_code']} "
                    "posting setup already has prepayment_account."
                )
