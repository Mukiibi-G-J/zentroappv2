from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from company.models import Company
from financials.enums import BalacingAccountType
from financials.models import G_LAccount, PaymentMethod

DEFAULT_METHODS = [
    {
        "code": "CASH",
        "description": "Cash",
        "bal_account_type": BalacingAccountType.GLAccount.value,
        "requires_amount_received": True,
    },
    {
        "code": "MOBILE_MONEY",
        "description": "Mobile Money",
        "bal_account_type": BalacingAccountType.GLAccount.value,
        "requires_amount_received": True,
    },
    {
        "code": "NOT_PAID",
        "description": "Not Paid Yet",
        "bal_account_type": BalacingAccountType.GLAccount.value,
        "requires_amount_received": False,
    },
]

CASH_GL_NOS = ("1000", "1010", "2930")


def _default_cash_gl_account() -> G_LAccount | None:
    for gl_no in CASH_GL_NOS:
        account = G_LAccount.objects.filter(no=gl_no).first()
        if account:
            return account
    return (
        G_LAccount.objects.filter(
            accounttype="Posting",
            accountcategory="Assets",
        )
        .order_by("no")
        .first()
    )


@transaction.atomic
def ensure_default_payment_methods() -> dict:
    """Create default payment methods when the tenant has none configured."""
    cash_gl = _default_cash_gl_account()
    if cash_gl is None:
        return {"created": 0, "skipped": True, "reason": "no_gl_account"}

    created = 0
    for method_data in DEFAULT_METHODS:
        _, was_created = PaymentMethod.objects.get_or_create(
            code=method_data["code"],
            defaults={
                **method_data,
                "bal_account_no": cash_gl,
            },
        )
        if was_created:
            created += 1

    return {"created": created, "skipped": False, "cash_gl": cash_gl.no}


class Command(BaseCommand):
    help = "Seed default financials payment methods for a tenant schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (default: all companies except public)",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Only seed tenants that currently have zero payment methods",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        only_empty = options.get("only_empty", False)

        if schema_name:
            schemas = [schema_name]
        else:
            schemas = list(
                Company.objects.exclude(schema_name="public")
                .order_by("schema_name")
                .values_list("schema_name", flat=True)
            )

        total_created = 0
        for schema in schemas:
            self.stdout.write(f"\nSchema: {schema}")
            with schema_context(schema):
                if only_empty and PaymentMethod.objects.exists():
                    self.stdout.write("  Skipped — payment methods already exist")
                    continue

                result = ensure_default_payment_methods()
                if result.get("skipped"):
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Skipped — {result.get('reason', 'unknown reason')}"
                        )
                    )
                    continue

                created = result["created"]
                total_created += created
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created {created} payment method(s) "
                        f"(cash G/L: {result['cash_gl']}, "
                        f"total now: {PaymentMethod.objects.count()})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {total_created} payment method(s) created across {len(schemas)} schema(s)."
            )
        )
