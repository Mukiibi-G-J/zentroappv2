"""
One-shot branch and dimension set backfill (idempotent) for the current schema.
Prefer applying migration dimension.0007 for all tenants; this command re-runs the same logic.
"""
from django.core.management.base import BaseCommand
from django.db import connection

try:
    from django_tenants.utils import get_public_schema_name, schema_context
except ImportError:
    schema_context = None
    get_public_schema_name = lambda: "public"  # noqa: E731

from dimension.backfill import run_branch_dimension_backfill


class Command(BaseCommand):
    help = (
        "Backfill null global_dimension_1 and dimension_set using the tenant's default branch. "
        "Use with tenant_command and --schema for a single tenant, or run in a tenant context."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-multiple-branch-values",
            action="store_true",
            help="If several DimensionValues exist for the branch dimension, use the first by code (dev only).",
        )
        parser.add_argument(
            "--no-audit",
            action="store_true",
            help=(
                "Do not write dimension_backfill_audit rows (faster, not reversible). "
                "Use when dimension.0007 is not applied yet and the audit table does not exist."
            ),
        )
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name; uses schema_context when django-tenants is available.",
        )

    def handle(self, *args, **options):
        allow_multi = options["allow_multiple_branch_values"]
        write_audit = not options["no_audit"]
        schema = (options.get("schema") or "").strip() or None

        def do():
            r, e = run_branch_dimension_backfill(
                allow_multiple_branch_values=allow_multi,
                write_audit=write_audit,
            )
            if e:
                self.stderr.write(self.style.ERROR(e))
                return
            sc = getattr(connection, "schema_name", None) or "?"
            self.stdout.write(
                self.style.SUCCESS(f"Branch dimension backfill in schema {sc}:")
            )
            for x in r:
                self.stdout.write(
                    f"  {x.label}  matched={x.matched_rows}  updated={x.updated}  {x.skipped or ''}"
                )

        if schema and schema_context:
            with schema_context(schema):
                do()
        else:
            do()
