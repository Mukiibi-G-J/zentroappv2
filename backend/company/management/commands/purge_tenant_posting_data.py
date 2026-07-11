from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

try:
    from django_tenants.utils import get_public_schema_name, schema_context, schema_exists
except ImportError:
    get_public_schema_name = None
    schema_context = None
    schema_exists = None


class Command(BaseCommand):
    help = (
        "Delete tenant transactional data (sales, value/item ledger, and G/L entries). "
        "Defaults to dry-run; use --apply to execute."
    )

    TARGET_MODELS = [
        # Sales transactional models
        ("sales", "SalesInvoiceLine", "SalesInvoiceLine"),
        ("sales", "SalesInvoice", "SalesInvoice"),
        ("sales", "SalesOrderLine", "SalesOrderLine"),
        ("sales", "SalesOrder", "SalesOrder"),
        ("sales", "PostedSalesInvoiceLine", "PostedSalesInvoiceLine"),
        ("sales", "PostedSalesInvoice", "PostedSalesInvoice"),
        ("sales", "SalesCreditMemoLine", "SalesCreditMemoLine"),
        ("sales", "SalesCreditMemo", "SalesCreditMemo"),
        ("sales", "DetailedCustomerLedgerEntry", "DetailedCustomerLedgerEntry"),
        ("sales", "CustomerLedgerEntry", "CustomerLedgerEntry"),
        # Item/value ledger models
        ("items", "ValueEntry", "ValueEntry"),
        ("items", "ItemLedgerEntries", "ItemLedgerEntries"),
        # G/L entries
        ("financials", "GeneralLedgerEntry", "GeneralLedgerEntry"),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="semuna",
            help=(
                "Tenant schema name to purge. Default: semuna. "
                "With tenant_command, this is optional."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Execute deletion. Without this flag, command runs as dry-run.",
        )

    def _resolve_schema(self, raw_schema: str) -> str:
        schema = (raw_schema or "").strip()

        if schema:
            if schema_context is None or schema_exists is None:
                raise CommandError(
                    "django-tenants is required to use --schema with this command."
                )
            if not schema_exists(schema):
                raise CommandError(f"Schema does not exist: {schema!r}")
            return schema

        if get_public_schema_name is None:
            raise CommandError("Pass --schema=... or run via tenant_command.")

        public = get_public_schema_name()
        current = getattr(connection, "schema_name", None)
        if current == public:
            raise CommandError(
                "Current schema is public. Use --schema or tenant_command for a tenant."
            )
        return current

    def _collect_counts(self):
        from django.apps import apps

        counts = []
        for app_label, model_name, label in self.TARGET_MODELS:
            model = apps.get_model(app_label, model_name)
            counts.append((label, model.objects.count(), model))
        return counts

    def handle(self, *args, **options):
        schema = self._resolve_schema(options.get("schema"))
        apply_changes = bool(options.get("apply"))

        def run():
            counts = self._collect_counts()
            total = sum(count for _, count, _ in counts)

            self.stdout.write(f"Target schema: {schema}")
            self.stdout.write("Objects selected for purge:")
            for label, count, _model in counts:
                self.stdout.write(f"  - {label}: {count}")
            self.stdout.write(f"  - TOTAL: {total}")

            if not apply_changes:
                self.stdout.write(
                    self.style.WARNING(
                        "Dry-run only. Re-run with --apply to delete these rows."
                    )
                )
                return

            with transaction.atomic():
                deleted_total = 0
                for label, _count, model in counts:
                    deleted, _ = model.objects.all().delete()
                    deleted_total += deleted
                    self.stdout.write(f"Deleted {deleted} rows from {label}.")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Purge completed in schema {schema!r}. Total rows deleted: {deleted_total}."
                )
            )

        if options.get("schema"):
            with schema_context(schema):
                run()
        else:
            run()
