"""
Read-only audit: count rows with null global_dimension_1, global_dimension_2, dimension_set per model per schema.
"""
import csv
import sys
from io import StringIO

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
    audit_entries,
    get_model_for_entry,
    model_has_field,
)


class Command(BaseCommand):
    help = (
        "Audit null branch dimensions per tenant schema (read-only). "
        "Use --schema=pilot to scan one tenant. "
        "Use --output-csv=path to write a CSV. "
        "Use --no-optional to skip authentication.CustomUser."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Single tenant schema name. If omitted, all tenant schemas are scanned.",
        )
        parser.add_argument(
            "--no-optional",
            action="store_true",
            help="Exclude optional models (e.g. CustomUser) from the audit.",
        )
        parser.add_argument(
            "--output-csv",
            type=str,
            help="If set, write results to this file path (UTF-8).",
        )

    def handle(self, *args, **options):
        include_optional = not options["no_optional"]
        entries = audit_entries(include_optional=include_optional)
        schema_filter = (options.get("schema") or "").strip() or None
        out_csv = options.get("output_csv") or None

        schemas = self._get_target_schemas(schema_filter)
        if not schemas:
            self.stderr.write(
                self.style.ERROR("No tenant schemas to scan. Check --schema or Company records.")
            )
            return

        rows_out = []
        for schema in schemas:
            if schema_context:
                with schema_context(schema):
                    rows_out.extend(self._audit_schema(schema, entries))
            else:
                self._set_search_path(schema)
                try:
                    rows_out.extend(self._audit_schema(schema, entries))
                finally:
                    self._set_search_path(get_public_schema_name())

        self._print_table(rows_out)
        if out_csv:
            self._write_csv(out_csv, rows_out)
            self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows_out)} row(s) to {out_csv}"))

    def _get_target_schemas(self, single: str | None) -> list[str]:
        if single:
            return [single]
        if not get_tenant_model:
            pub = get_public_schema_name() if get_public_schema_name else "public"
            self.stdout.write(
                self.style.WARNING(
                    "django_tenants not available; set search_path manually or use --schema=..."
                )
            )
            return [pub]
        Company = get_tenant_model()
        return list(Company.objects.exclude(schema_name=get_public_schema_name()).values_list("schema_name", flat=True).order_by("schema_name"))

    def _set_search_path(self, schema: str):
        with connection.cursor() as c:
            c.execute("SET search_path TO %s, public", [schema])

    def _audit_schema(self, schema_name: str, entries):
        rows = []
        for entry in entries:
            try:
                model = get_model_for_entry(entry)
            except LookupError as e:
                rows.append(
                    {
                        "schema_name": schema_name,
                        "app_label": entry.app_label,
                        "model": entry.model_name,
                        "db_table": "?",
                        "row_count": 0,
                        "null_g1": 0,
                        "null_g2": 0,
                        "null_ds": 0,
                        "has_g2": False,
                        "has_ds": entry.has_dimension_set,
                        "error": str(e),
                    }
                )
                continue
            if not model._meta.managed or model._meta.proxy:
                continue
            if not model_has_field(model, "global_dimension_1"):
                continue
            has_g2 = model_has_field(model, "global_dimension_2")
            has_ds = model_has_field(model, "dimension_set")
            db_table = model._meta.db_table

            table_exists = self._table_exists_in_current_schema(db_table)
            if not table_exists:
                rows.append(
                    {
                        "schema_name": schema_name,
                        "app_label": entry.app_label,
                        "model": entry.model_name,
                        "db_table": db_table,
                        "row_count": 0,
                        "null_g1": 0,
                        "null_g2": 0,
                        "null_ds": 0,
                        "has_g2": has_g2,
                        "has_ds": has_ds,
                        "error": "MISSING_TABLE",
                    }
                )
                continue

            cols = self._columns_in_current_schema_table(db_table)
            required_cols = {"global_dimension_1_id"}
            if has_g2:
                required_cols.add("global_dimension_2_id")
            if has_ds:
                required_cols.add("dimension_set_id")
            missing_cols = sorted(c for c in required_cols if c not in cols)
            if missing_cols:
                rows.append(
                    {
                        "schema_name": schema_name,
                        "app_label": entry.app_label,
                        "model": entry.model_name,
                        "db_table": db_table,
                        "row_count": 0,
                        "null_g1": 0,
                        "null_g2": 0,
                        "null_ds": 0,
                        "has_g2": has_g2,
                        "has_ds": has_ds,
                        "error": f"MISSING_COLUMN: {', '.join(missing_cols)}",
                    }
                )
                continue
            # COUNT(*) can succeed while dimension columns are missing (schema drift);
            # null filters need the same try/except.
            try:
                total = model.objects.count()
                null_g1 = model.objects.filter(
                    global_dimension_1__isnull=True
                ).count()
                null_g2 = (
                    model.objects.filter(global_dimension_2__isnull=True).count()
                    if has_g2
                    else 0
                )
                null_ds = (
                    model.objects.filter(dimension_set__isnull=True).count()
                    if has_ds
                    else 0
                )
            except (ProgrammingError, DatabaseError) as e:
                rows.append(
                    {
                        "schema_name": schema_name,
                        "app_label": entry.app_label,
                        "model": entry.model_name,
                        "db_table": db_table,
                        "row_count": 0,
                        "null_g1": 0,
                        "null_g2": 0,
                        "null_ds": 0,
                        "has_g2": has_g2,
                        "has_ds": has_ds,
                        "error": str(e)[:200],
                    }
                )
                continue
            rows.append(
                {
                    "schema_name": schema_name,
                    "app_label": entry.app_label,
                    "model": entry.model_name,
                    "db_table": db_table,
                    "row_count": total,
                    "null_g1": null_g1,
                    "null_g2": null_g2,
                    "null_ds": null_ds,
                    "has_g2": has_g2,
                    "has_ds": has_ds,
                    "error": "",
                }
            )
        return rows

    def _table_exists_in_current_schema(self, table_name: str) -> bool:
        """
        True if table exists in the current tenant schema.
        Uses information_schema to avoid quoting pitfalls.
        """
        try:
            with connection.cursor() as c:
                c.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                    LIMIT 1
                    """,
                    [table_name],
                )
                return c.fetchone() is not None
        except Exception:
            # If introspection fails, fall back to optimistic behavior; caller still has ORM try/except.
            return True

    def _columns_in_current_schema_table(self, table_name: str) -> set[str]:
        """
        Return set of column_name values for a table in current schema.
        If introspection fails, return empty set to force a safe "missing columns" report.
        """
        try:
            with connection.cursor() as c:
                c.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                    """,
                    [table_name],
                )
                return {r[0] for r in c.fetchall()}
        except Exception:
            return set()

    def _print_table(self, rows_out: list):
        headers = [
            "schema_name",
            "app_label",
            "model",
            "db_table",
            "row_count",
            "null_g1",
            "null_g2",
            "null_ds",
            "has_g2",
            "has_ds",
            "error",
        ]
        w = [max(len(h), 12) for h in headers]
        line = " | ".join(h.ljust(w[i]) for i, h in enumerate(headers))
        self.stdout.write(line)
        self.stdout.write("-" * len(line))
        for r in rows_out:
            vals = [str(r.get(h, "")) for h in headers]
            self.stdout.write(" | ".join(vals[i].ljust(w[i]) for i in range(len(headers))))

    def _write_csv(self, path: str, rows_out: list):
        fieldnames = [
            "schema_name",
            "app_label",
            "model",
            "db_table",
            "row_count",
            "null_g1",
            "null_g2",
            "null_ds",
            "has_g2",
            "has_ds",
            "error",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows_out:
                w.writerow({k: r.get(k, "") for k in fieldnames})
