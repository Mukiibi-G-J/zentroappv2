from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from company.models import Company
from financials.ledger_application import (
    _vendor_payment_fk_column,
    backfill_customer_ledger_applies_to_ids,
    backfill_vendor_ledger_applies_to_ids,
)


class Command(BaseCommand):
    help = (
        "Backfill applies_to_id on invoice/credit ledger rows from legacy payment links "
        "and payment journal apply targets (never on Payment rows)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (default: all tenants)",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        schemas = [schema] if schema else list(Company.objects.values_list("schema_name", flat=True))

        total_vendor = 0
        total_customer = 0
        for tenant_schema in schemas:
            with schema_context(tenant_schema):
                fk_col = _vendor_payment_fk_column("default")
                if fk_col is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{tenant_schema}: no legacy payment FK column "
                            f"(run: python manage.py migrate_schemas --schema={tenant_schema} purchases)"
                        )
                    )
                vendor_count = backfill_vendor_ledger_applies_to_ids()
                customer_count = backfill_customer_ledger_applies_to_ids()
                total_vendor += vendor_count
                total_customer += customer_count
                self.stdout.write(
                    f"{tenant_schema}: vendor={vendor_count}, customer={customer_count}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — updated {total_vendor} vendor and {total_customer} customer ledger row(s)."
            )
        )
