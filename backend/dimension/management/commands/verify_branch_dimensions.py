"""
Exit 0 if no null global_dimension_1 (and dimension_set where applicable) in backfill registry.
Run after backfill; use in CI with tenant schema context.
"""
import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import DatabaseError, ProgrammingError

try:
    from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context
except ImportError:
    schema_context = None
    get_tenant_model = None
    get_public_schema_name = lambda: "public"  # noqa: E731

from dimension.branch_dimension_registry import (
    backfill_entries,
    get_model_for_entry,
    model_has_field,
)


class Command(BaseCommand):
    help = "Verify all registry rows have branch dimensions set. Exits 1 on any nulls."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Single tenant schema; if omitted, check all non-public tenant schemas.",
        )

    def handle(self, *args, **options):
        schema_arg = (options.get("schema") or "").strip() or None
        schemas = self._schemas(schema_arg)
        total_issues = 0
        for schema in schemas:
            if schema_context:
                with schema_context(schema):
                    total_issues += self._check_one(schema)
            else:
                self._set_path(schema)
                try:
                    total_issues += self._check_one(schema)
                finally:
                    self._set_path(get_public_schema_name() if get_public_schema_name else "public")
        if total_issues:
            self.stderr.write(
                self.style.ERROR(
                    f"Verification failed: {total_issues} null field(s) across schema(s). "
                    "Run audit_dimension_nulls for details."
                )
            )
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("Branch dimension verification passed (no nulls in registry)."))

    def _schemas(self, one: str | None):
        if one:
            return [one]
        if not get_tenant_model:
            return [get_public_schema_name() if get_public_schema_name else "public"]
        Company = get_tenant_model()
        return list(
            Company.objects.exclude(schema_name=get_public_schema_name())
            .values_list("schema_name", flat=True)
            .order_by("schema_name")
        )

    def _set_path(self, schema: str):
        with connection.cursor() as c:
            c.execute("SET search_path TO %s, public", [schema])

    def _check_one(self, schema_name: str) -> int:
        issues = 0
        for entry in backfill_entries():
            try:
                model = get_model_for_entry(entry)
            except LookupError:
                continue
            if not model_has_field(model, "global_dimension_1") or not model._meta.managed or model._meta.proxy:
                continue
            has_ds = model_has_field(model, "dimension_set") and entry.has_dimension_set
            try:
                n1 = model.objects.filter(global_dimension_1__isnull=True).count()
            except (ProgrammingError, DatabaseError) as e:
                self.stdout.write(
                    self.style.WARNING(f"{schema_name} {entry.model_name}: {e}")
                )
                continue
            if n1:
                self.stdout.write(
                    self.style.ERROR(
                        f"{schema_name} {entry.app_label}.{entry.model_name}: {n1} null global_dimension_1"
                    )
                )
                issues += n1
            if has_ds:
                n2 = model.objects.filter(dimension_set__isnull=True).count()
                if n2:
                    self.stdout.write(
                        self.style.ERROR(
                            f"{schema_name} {entry.app_label}.{entry.model_name}: {n2} null dimension_set"
                        )
                    )
                    issues += n2
        return issues
