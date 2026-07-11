from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from items.enums import EntryType
from items.models import ItemLedgerEntries


class Command(BaseCommand):
    help = "Fix Item Ledger Entries with entry_type='Sale' to use 'Sales'"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant schema name (optional). If omitted, runs for all tenants.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be updated without changing data.",
        )

    def _fix_entry_types(self, schema_name: str, dry_run: bool):
        with schema_context(schema_name):
            queryset = ItemLedgerEntries.objects.filter(entry_type__iexact="Sale")
            total = queryset.count()

            if dry_run:
                self.stdout.write(
                    f"Tenant: {schema_name} - Would update {total} entries"
                )
                return

            updated = queryset.update(entry_type=EntryType.Sales.value)
            self.stdout.write(
                self.style.SUCCESS(f"Tenant: {schema_name} - Updated {updated} entries")
            )

    def handle(self, *args, **options):
        tenant_schema = options.get("tenant")
        dry_run = options.get("dry_run", False)

        if tenant_schema:
            self._fix_entry_types(tenant_schema, dry_run)
            return

        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name="public")

        for tenant in tenants:
            self._fix_entry_types(tenant.schema_name, dry_run)
