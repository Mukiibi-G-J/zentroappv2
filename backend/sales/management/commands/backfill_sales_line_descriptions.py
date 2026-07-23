"""
Backfill blank sales line descriptions from the linked item/resource.

Sales History (PostedSalesInvoiceLine) and open SalesInvoiceLine rows often have
item_no but an empty description when POS sent description=''.

Usage:
  python manage.py tenant_command backfill_sales_line_descriptions --schema=primewise --dry-run
  python manage.py tenant_command backfill_sales_line_descriptions --schema=primewise
  python manage.py backfill_sales_line_descriptions --all-tenants
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q

try:
    from django_tenants.utils import get_tenant_model, schema_context
except ImportError:
    get_tenant_model = None
    schema_context = None

from items.models import Item
from sales.models import (
    PostedSalesInvoiceLine,
    SalesCreditMemoLine,
    SalesInvoiceLine,
    SalesOrderLine,
)

BLANK = Q(description="") | Q(description__isnull=True)


def _blank_qs(model):
    return model.objects.filter(BLANK)


def _count_candidates(model):
    item_n = _blank_qs(model).filter(item__isnull=False).count()
    resource_n = 0
    if any(f.name == "resource" for f in model._meta.get_fields()):
        resource_n = _blank_qs(model).filter(resource__isnull=False).count()
    return item_n, resource_n


def _quote(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _backfill_with_sql(line_model, *, resource_join: bool = True) -> dict:
    """
    Fast PostgreSQL UPDATE … FROM for blank descriptions.
    Uses each model's db_table (Item uses custom table name `items`).
    """
    line_table = _quote(line_model._meta.db_table)
    item_table = _quote(Item._meta.db_table)
    item_pk = _quote(Item._meta.pk.column)  # Item PK is `no`, not `id`
    updated = {"item": 0, "resource": 0}

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {line_table} AS l
            SET description = i.item_name
            FROM {item_table} AS i
            WHERE l.item_id = i.{item_pk}
              AND (l.description IS NULL OR btrim(l.description) = '')
              AND i.item_name IS NOT NULL
              AND btrim(i.item_name) <> ''
            """
        )
        updated["item"] = cursor.rowcount

        if resource_join:
            from resources.models import Resource

            resource_table = _quote(Resource._meta.db_table)
            resource_pk = _quote(Resource._meta.pk.column)
            cursor.execute(
                f"""
                UPDATE {line_table} AS l
                SET description = r.name
                FROM {resource_table} AS r
                WHERE l.resource_id = r.{resource_pk}
                  AND (l.description IS NULL OR btrim(l.description) = '')
                  AND r.name IS NOT NULL
                  AND btrim(r.name) <> ''
                """
            )
            updated["resource"] = cursor.rowcount
    return updated


class Command(BaseCommand):
    help = (
        "Backfill blank sales line descriptions from item.item_name / resource.name "
        "(PostedSalesInvoiceLine, SalesInvoiceLine, SalesOrderLine, SalesCreditMemoLine)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be updated without writing.",
        )
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (also used via tenant_command --schema).",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Run for every non-public tenant schema.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        schema = (options.get("schema") or "").strip() or None
        all_tenants = options["all_tenants"]

        if all_tenants and schema_context and get_tenant_model:
            Tenant = get_tenant_model()
            schemas = list(
                Tenant.objects.exclude(schema_name="public").values_list(
                    "schema_name", flat=True
                )
            )
            for name in schemas:
                with schema_context(name):
                    self._run_schema(name, dry_run)
            return

        if schema and schema_context:
            with schema_context(schema):
                self._run_schema(schema, dry_run)
            return

        # Active connection schema (tenant_command already switched)
        sc = getattr(connection, "schema_name", None) or "?"
        self._run_schema(sc, dry_run)

    def _run_schema(self, schema_name: str, dry_run: bool):
        targets = [
            ("PostedSalesInvoiceLine", PostedSalesInvoiceLine, True),
            ("SalesInvoiceLine", SalesInvoiceLine, True),
            ("SalesOrderLine", SalesOrderLine, True),
            ("SalesCreditMemoLine", SalesCreditMemoLine, False),
        ]

        self.stdout.write(f"Schema {schema_name}:")
        total_would = 0
        total_done = 0

        for label, model, has_resource in targets:
            try:
                item_n, resource_n = _count_candidates(model)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  skip {label}: {exc}"))
                continue

            would = item_n + resource_n
            total_would += would
            self.stdout.write(
                f"  {label}: blank with item={item_n}, resource={resource_n}"
            )

            if dry_run or would == 0:
                continue

            updated = _backfill_with_sql(model, resource_join=has_resource)
            done = updated["item"] + updated["resource"]
            total_done += done
            self.stdout.write(
                self.style.SUCCESS(
                    f"    updated item={updated['item']}, resource={updated['resource']}"
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"  dry-run total candidates: {total_would}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  done: updated {total_done} rows")
            )
