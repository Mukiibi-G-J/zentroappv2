import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name, schema_context

from company.models import Company
from financials.models import (
    FinancialReport,
    FinancialReportColumnGroup,
    FinancialReportColumnLine,
)

DATA_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "income_statement_column_definition.json"
)


def _active_tenant_schema() -> str | None:
    """When invoked via `tenant_command`, the connection tenant is already set."""
    tenant = getattr(connection, 'tenant', None)
    schema_name = getattr(tenant, 'schema_name', None)
    if schema_name and schema_name != get_public_schema_name():
        return schema_name
    return None


def _load_definition() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _column_line_defaults(line: dict) -> dict:
    return {
        "column_no": line.get("column_no", str(line["line_no"])),
        "column_header": line.get("column_header", ""),
        "column_type": line.get("column_type", "Net Change"),
        "comparison_period_formula": line.get("comparison_period_formula", "0M"),
        "amount_type": line.get("amount_type", ""),
        "formula": line.get("formula", ""),
        "show_opposite_sign": line.get("show_opposite_sign", False),
    }


@transaction.atomic
def seed_income_statement_column_definition(*, clear: bool = False) -> dict:
    definition = _load_definition()
    column_group_data = definition["column_group"]

    column_group, column_group_created = FinancialReportColumnGroup.objects.update_or_create(
        name=column_group_data["name"],
        defaults={"description": column_group_data.get("description", "")},
    )

    if clear:
        FinancialReportColumnLine.objects.filter(column_group=column_group).delete()

    column_created = 0
    column_updated = 0
    for line in definition.get("column_lines", []):
        _, created = FinancialReportColumnLine.objects.update_or_create(
            column_group=column_group,
            line_no=line["line_no"],
            defaults=_column_line_defaults(line),
        )
        if created:
            column_created += 1
        else:
            column_updated += 1

    report_linked = False
    link_data = definition.get("financial_report_link")
    if link_data:
        report_name = link_data["name"]
        try:
            report = FinancialReport.objects.get(name=report_name)
            report.column_definition = column_group
            report.save(update_fields=["column_definition"])
            report_linked = True
        except FinancialReport.DoesNotExist:
            pass

    return {
        "column_group": column_group.name,
        "column_group_created": column_group_created,
        "column_lines_created": column_created,
        "column_lines_updated": column_updated,
        "total_column_lines": FinancialReportColumnLine.objects.filter(
            column_group=column_group
        ).count(),
        "financial_report_linked": report_linked,
    }


class Command(BaseCommand):
    help = "Seed the MONTHLY column definition for the profit & loss report"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (default: all companies except public)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing MONTHLY column lines before seeding",
        )

    def handle(self, *args, **options):
        target = options.get("schema") or _active_tenant_schema()
        clear = options.get("clear", False)

        if target:
            schemas = [target]
        else:
            schemas = list(
                Company.objects.exclude(schema_name="public")
                .order_by("schema_name")
                .values_list("schema_name", flat=True)
            )

        errors = []
        for schema in schemas:
            self.stdout.write(f"\nSchema: {schema}")
            try:
                with schema_context(schema):
                    result = seed_income_statement_column_definition(clear=clear)
            except Exception as exc:
                errors.append((schema, exc))
                self.stdout.write(self.style.ERROR(f"  Failed: {exc}"))
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Column definition {result['column_group']}: "
                    f"{result['total_column_lines']} column(s) "
                    f"({result['column_lines_created']} created, "
                    f"{result['column_lines_updated']} updated)"
                )
            )
            if result["financial_report_linked"]:
                self.stdout.write("  Linked to financial report INCOME")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "  Financial report INCOME not found — run row seed first"
                    )
                )

        if errors:
            detail = "; ".join(f"{name}: {err}" for name, err in errors)
            raise CommandError(f"{len(errors)} schema(s) failed — {detail}")

        if target:
            self.stdout.write(self.style.SUCCESS(f"\nDone — schema: {target}"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone — seeded column definition across {len(schemas)} schema(s)."
                )
            )
