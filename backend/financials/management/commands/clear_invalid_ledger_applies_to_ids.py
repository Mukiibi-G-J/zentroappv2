from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from company.models import Company
from payments.journal_application import clear_invalid_payment_ledger_applies_to_ids


class Command(BaseCommand):
    help = (
        "Clear applies_to_id wrongly stored on Payment/Refund vendor and customer ledger rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (default: all tenants)",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        schemas = (
            [schema]
            if schema
            else list(Company.objects.values_list("schema_name", flat=True))
        )

        total = 0
        for tenant_schema in schemas:
            with schema_context(tenant_schema):
                cleared = clear_invalid_payment_ledger_applies_to_ids()
                total += cleared
                self.stdout.write(f"{tenant_schema}: cleared {cleared} payment row(s)")

        self.stdout.write(
            self.style.SUCCESS(f"Done — cleared applies_to_id on {total} payment row(s).")
        )
