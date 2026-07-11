"""
Seed VAT posting groups and VAT posting setup (BC-style).

Run: python manage.py tenant_command seed_vat_posting_setup --schema=<schema>

Creates:
- VAT Business Posting Groups: DOMESTIC, EU (optional), NON_EU (optional)
- VAT Product Posting Groups: STANDARD (18%), ZERO (0%), EXEMPT (0%)
- VAT G/L accounts if missing: 3110 (VAT Output), 3111 (VAT Input)
- VAT Posting Setup: DOMESTIC + STANDARD = 18% with sales/purchase VAT accounts
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import G_LAccount
from financials.enums import G_L_Account_Type, INCOME_BALANCE, G_L_Account_Category, DEBIT_CREDIT
from postings.models import (
    VATBusinessPostingGroup,
    VATProductPostingGroup,
    VATPostingSetup,
)


def ensure_vat_gl_accounts():
    """Create VAT G/L accounts if they don't exist. Returns (sales_vat, purchase_vat)."""
    defaults = {
        "name": "",
        "indentation": 2,
        "income_balance": INCOME_BALANCE.Balance.value,
        "accountcategory": G_L_Account_Category.Liabilities.value,
        "debit_credit": DEBIT_CREDIT.Both.value,
        "accounttype": G_L_Account_Type.Posting.value,
        "totaling": None,
        "direct_posting": True,
        "blocked": False,
    }

    sales_vat, _ = G_LAccount.objects.get_or_create(
        no="3110",
        defaults={**defaults, "name": "VAT Output / Sales VAT"},
    )
    purchase_vat, _ = G_LAccount.objects.get_or_create(
        no="3111",
        defaults={**defaults, "name": "VAT Input / Purchase VAT"},
    )
    return sales_vat, purchase_vat


@transaction.atomic
def seed_vat_posting_setup():
    """Create VAT posting groups and setup. Idempotent."""
    sales_vat, purchase_vat = ensure_vat_gl_accounts()

    # VAT Business Posting Groups
    vat_bus_domestic, _ = VATBusinessPostingGroup.objects.get_or_create(
        code="DOMESTIC",
        defaults={"description": "Domestic", "default": True},
    )
    VATBusinessPostingGroup.objects.get_or_create(
        code="EU",
        defaults={"description": "European Union", "default": False},
    )
    VATBusinessPostingGroup.objects.get_or_create(
        code="NON_EU",
        defaults={"description": "Non-EU", "default": False},
    )

    # VAT Product Posting Groups
    vat_prod_standard, _ = VATProductPostingGroup.objects.get_or_create(
        code="STANDARD",
        defaults={"description": "Standard 18%", "default": True},
    )
    VATProductPostingGroup.objects.get_or_create(
        code="ZERO",
        defaults={"description": "Zero Rate", "default": False},
    )
    VATProductPostingGroup.objects.get_or_create(
        code="EXEMPT",
        defaults={"description": "Exempt", "default": False},
    )

    # VAT Posting Setup: DOMESTIC + STANDARD = 18%
    setup, created = VATPostingSetup.objects.get_or_create(
        vat_business_posting_group=vat_bus_domestic,
        vat_product_posting_group=vat_prod_standard,
        defaults={
            "vat_percent": Decimal("18.00"),
            "vat_calculation_type": "Normal",
            "sales_vat_account": sales_vat,
            "purchase_vat_account": purchase_vat,
            "vat_identifier": "VAT18",
        },
    )
    if not created:
        # Update accounts if setup existed but accounts were missing
        if not setup.sales_vat_account:
            setup.sales_vat_account = sales_vat
        if not setup.purchase_vat_account:
            setup.purchase_vat_account = purchase_vat
        setup.save(update_fields=["sales_vat_account", "purchase_vat_account", "updated_at"])

    # DOMESTIC + ZERO = 0%
    vat_prod_zero = VATProductPostingGroup.objects.get(code="ZERO")
    VATPostingSetup.objects.get_or_create(
        vat_business_posting_group=vat_bus_domestic,
        vat_product_posting_group=vat_prod_zero,
        defaults={
            "vat_percent": Decimal("0.00"),
            "vat_calculation_type": "Normal",
            "sales_vat_account": sales_vat,
            "purchase_vat_account": purchase_vat,
            "vat_identifier": "VAT0",
        },
    )


class Command(BaseCommand):
    help = "Seed VAT posting groups and VAT posting setup (BC-style)"

    def handle(self, *args, **options):
        seed_vat_posting_setup()
        self.stdout.write(
            self.style.SUCCESS("VAT posting setup seeded successfully. Enable VAT in General Ledger Setup.")
        )
