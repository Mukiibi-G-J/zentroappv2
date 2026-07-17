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
    FinancialReportRowGroup,
    FinancialReportRowLine,
    G_LAccount,
)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "income_statement_row_definition.json"


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


def _posting_account_range(
    *,
    category: str | None = None,
    prefix: str | None = None,
) -> str | None:
    queryset = G_LAccount.objects.filter(
        income_balance="Income Statement",
        accounttype="Posting",
    )
    if category:
        queryset = queryset.filter(accountcategory=category)
    if prefix:
        queryset = queryset.filter(no__startswith=prefix)

    account_nos = sorted(queryset.values_list("no", flat=True))
    if not account_nos:
        return None
    if len(account_nos) == 1:
        return account_nos[0]
    return f"{account_nos[0]}|{account_nos[-1]}"


def _resolve_totaling(line: dict) -> str:
    fallback = line.get("totaling") or ""
    category = line.get("account_category")
    prefix = line.get("account_prefix")
    if not category and not prefix:
        return fallback

    resolved = _posting_account_range(category=category, prefix=prefix)
    return resolved or fallback


def _default_show(row_type: str | None) -> str:
    if row_type == "Header":
        return "Yes"
    return "If Amount Not Zero"


def _line_payload(line: dict, row_group: FinancialReportRowGroup) -> dict:
    payload = {
        key: line[key]
        for key in (
            "line_no",
            "row_no",
            "description",
            "row_type",
            "row_amount_basis",
            "totaling_type",
            "amount_type",
            "show_opposite_sign",
            "bold",
            "indentation",
            "show",
        )
        if key in line
    }
    payload["show"] = line.get("show") or _default_show(line.get("row_type"))
    payload["totaling"] = _resolve_totaling(line)
    payload["row_group"] = row_group
    return payload


@transaction.atomic
def seed_income_statement_row_definition(*, clear: bool = False) -> dict:
    definition = _load_definition()
    row_group_data = definition["row_group"]
    column_group_data = definition["column_group"]

    row_group, row_group_created = FinancialReportRowGroup.objects.update_or_create(
        name=row_group_data["name"],
        defaults={"description": row_group_data.get("description", "")},
    )

    column_group, column_group_created = FinancialReportColumnGroup.objects.update_or_create(
        name=column_group_data["name"],
        defaults={"description": column_group_data.get("description", "")},
    )

    if clear:
        FinancialReportRowLine.objects.filter(row_group=row_group).delete()
        FinancialReportColumnLine.objects.filter(column_group=column_group).delete()

    row_created = 0
    row_updated = 0
    for line in definition["row_lines"]:
        payload = _line_payload(line, row_group)
        line_no = payload.pop("line_no")
        _, created = FinancialReportRowLine.objects.update_or_create(
            row_group=row_group,
            line_no=line_no,
            defaults=payload,
        )
        if created:
            row_created += 1
        else:
            row_updated += 1

    column_created = 0
    column_updated = 0
    for line in definition.get("column_lines", []):
        _, created = FinancialReportColumnLine.objects.update_or_create(
            column_group=column_group,
            line_no=line["line_no"],
            defaults={
                "column_no": line.get("column_no", str(line["line_no"])),
                "column_header": line.get("column_header", ""),
                "column_type": line.get("column_type", "Net Change"),
                "comparison_period_formula": line.get("comparison_period_formula", "0M"),
                "amount_type": line.get("amount_type", ""),
                "formula": line.get("formula", ""),
                "show_opposite_sign": line.get("show_opposite_sign", False),
            },
        )
        if created:
            column_created += 1
        else:
            column_updated += 1

    report_data = definition.get("financial_report")
    report_created = False
    if report_data:
        _, report_created = FinancialReport.objects.update_or_create(
            name=report_data["name"],
            defaults={
                "description": report_data.get("description", ""),
                "period_type": report_data.get("period_type", "Month"),
                "show_all_lines": bool(report_data.get("show_all_lines", False)),
                "row_definition": row_group,
                "column_definition": column_group,
            },
        )

    return {
        "row_group": row_group.name,
        "column_group": column_group.name,
        "row_group_created": row_group_created,
        "column_group_created": column_group_created,
        "row_lines_created": row_created,
        "row_lines_updated": row_updated,
        "column_lines_created": column_created,
        "column_lines_updated": column_updated,
        "total_column_lines": FinancialReportColumnLine.objects.filter(
            column_group=column_group
        ).count(),
        "financial_report_created": report_created,
        "total_row_lines": FinancialReportRowLine.objects.filter(row_group=row_group).count(),
    }


class Command(BaseCommand):
    help = "Seed the INCOME statement row definition, column layout, and financial report setup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (default: all companies except public)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing INCOME/STD lines before seeding",
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
                    result = seed_income_statement_row_definition(clear=clear)
            except Exception as exc:
                errors.append((schema, exc))
                self.stdout.write(self.style.ERROR(f"  Failed: {exc}"))
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    "  Row definition "
                    f"{result['row_group']}: "
                    f"{result['total_row_lines']} line(s) "
                    f"({result['row_lines_created']} created, "
                    f"{result['row_lines_updated']} updated)"
                )
            )
            self.stdout.write(
                f"  Column definition {result['column_group']}: "
                f"{result['total_column_lines']} column(s) "
                f"({result['column_lines_created']} created, "
                f"{result['column_lines_updated']} updated)"
            )
            if result["financial_report_created"]:
                self.stdout.write("  Financial report INCOME created")
            else:
                self.stdout.write("  Financial report INCOME updated")

        if errors:
            detail = "; ".join(f"{name}: {err}" for name, err in errors)
            raise CommandError(f"{len(errors)} schema(s) failed — {detail}")

        if target:
            self.stdout.write(self.style.SUCCESS(f"\nDone — schema: {target}"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone — seeded income statement row definition across {len(schemas)} schema(s)."
                )
            )
