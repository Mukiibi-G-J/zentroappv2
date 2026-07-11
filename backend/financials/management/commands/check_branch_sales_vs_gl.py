"""
Compare posted sales (Customer Ledger) to Sales-posting G/L entries for one branch.

Usage:
  python manage.py tenant_command check_branch_sales_vs_gl --schema=primewise --branch-code=MWANJARI

Optional (slower):
  --scan-null-branch-gl   Full-table scan for Sales G/L with NULL branch
  --skip-doc-type-breakdown  Skip document_type grouping
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum, Count

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = (
        "Sum posted invoice amounts on Customer Ledger vs Sales G/L (Income) for a branch."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (tenant_command passes this; optional if context is set).",
        )
        parser.add_argument(
            "--branch-code",
            type=str,
            default="MWANJARI",
            help="Branch DimensionValue code or part of description (case-insensitive).",
        )
        parser.add_argument(
            "--scan-null-branch-gl",
            action="store_true",
            help=(
                "Also scan ALL Sales G/L lines with NULL branch (can be very slow on large DBs). "
                "Default off so the command stays branch-scoped only."
            ),
        )
        parser.add_argument(
            "--skip-doc-type-breakdown",
            action="store_true",
            help="Skip the document_type grouping query (saves one round trip).",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        branch_code = (options.get("branch_code") or "").strip()
        scan_null_branch = options.get("scan_null_branch_gl", False)
        skip_doc_breakdown = options.get("skip_doc_type_breakdown", False)

        def run():
            import sys

            from dimension.models import DimensionValue
            from financials.models import GeneralLedgerEntry
            from financials.enums import DOCUMENT_TYPE as GL_DOC_TYPE
            from sales.models import CustomerLedgerEntry, SalesInvoice

            self.stdout.write("\n=== Branch sales vs G/L (Sales posting) ===\n")
            self.stdout.write("Resolving branch…\n")
            sys.stdout.flush()

            branch = (
                DimensionValue.objects.filter(
                    Q(code__iexact=branch_code) | Q(description__icontains=branch_code)
                )
                .only("id", "code", "description")
                .order_by("id")
                .first()
            )
            if not branch:
                self.stdout.write(
                    self.style.ERROR(
                        f"No DimensionValue matched --branch-code={branch_code!r}. "
                        "Try the exact code from Dimension Values."
                    )
                )
                return

            self.stdout.write(
                f"Branch: id={branch.id} code={branch.code!r} description={branch.description!r}\n"
            )
            sys.stdout.flush()

            # --- Customer sub-ledger: posted invoices ---
            self.stdout.write("Querying Customer Ledger…\n")
            sys.stdout.flush()
            cle_base = CustomerLedgerEntry.objects.filter(
                global_dimension_1_id=branch.id,
                document_type=GL_DOC_TYPE.Invoice.value,
                reversed=False,
            )
            cle_agg = cle_base.aggregate(
                n=Count("id"),
                sum_amount=Sum("amount"),
                sum_sales=Sum("sales"),
            )
            self.stdout.write("Customer Ledger — Invoice rows (not reversed):")
            self.stdout.write(f"  Count: {cle_agg['n'] or 0}")
            self.stdout.write(f"  Sum(amount):  {cle_agg['sum_amount'] or 0}")
            self.stdout.write(f"  Sum(sales):   {cle_agg['sum_sales'] or 0}")

            self.stdout.write("Querying posted SalesInvoice count…\n")
            sys.stdout.flush()
            posted_inv_count = SalesInvoice.objects.filter(
                global_dimension_1_id=branch.id, status="Posted"
            ).count()
            self.stdout.write(
                f"\nSalesInvoice headers: Posted count = {posted_inv_count}"
            )

            # --- G/L: Sales posting — one aggregate query (branch-scoped) ---
            self.stdout.write("Querying G/L (Sales posting, this branch)…\n")
            sys.stdout.flush()
            gl_sales_base = GeneralLedgerEntry.objects.filter(
                global_dimension_1_id=branch.id,
                general_posting_type="Sales",
                reversed=False,
            )
            income_q = Q(gl_account__accountcategory="Income")
            acct6110_q = Q(gl_account__no="6110")
            gl_agg = gl_sales_base.aggregate(
                n_all=Count("id"),
                sum_all=Sum("amount"),
                n_income=Count("id", filter=income_q),
                sum_income=Sum("amount", filter=income_q),
                n_6110=Count("id", filter=acct6110_q),
                sum_6110=Sum("amount", filter=acct6110_q),
            )

            self.stdout.write("\nG/L entries — general_posting_type=Sales (not reversed):")
            self.stdout.write(
                f"  All accounts: count={gl_agg['n_all'] or 0}, Sum(amount)={gl_agg['sum_all'] or 0}"
            )
            self.stdout.write(
                f"  Income only:  count={gl_agg['n_income'] or 0}, Sum(amount)={gl_agg['sum_income'] or 0}"
            )
            self.stdout.write(
                f"  Account 6110:  count={gl_agg['n_6110'] or 0}, Sum(amount)={gl_agg['sum_6110'] or 0}"
            )

            # Full-table scan unless opted in — this was the main slowdown on large tenants.
            if scan_null_branch:
                self.stdout.write(
                    "\nScanning Sales G/L with NULL branch (slow)…\n"
                )
                sys.stdout.flush()
                gl_missing_dim = GeneralLedgerEntry.objects.filter(
                    general_posting_type="Sales",
                    reversed=False,
                    global_dimension_1__isnull=True,
                ).aggregate(n=Count("id"), sum_amt=Sum("amount"))
                if gl_missing_dim["n"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\nWARNING: {gl_missing_dim['n']} Sales G/L rows have NULL global_dimension_1 "
                            f"(Sum amount)={gl_missing_dim['sum_amt'] or 0} — branch filter on COA will ignore these."
                        )
                    )
                else:
                    self.stdout.write("  No NULL-branch Sales G/L rows.")
            else:
                self.stdout.write(
                    "\n(NULL-branch Sales G/L scan skipped; use --scan-null-branch-gl if needed.)\n"
                )

            # --- G/L document types mix (informational) ---
            if not skip_doc_breakdown:
                self.stdout.write("Grouping Sales G/L by document_type…\n")
                sys.stdout.flush()
                dt_counts = (
                    gl_sales_base.values("document_type")
                    .annotate(c=Count("id"))
                    .order_by("-c")
                )
                self.stdout.write("\nSales G/L rows by document_type:")
                for row in dt_counts[:15]:
                    self.stdout.write(f"  {row['document_type']!r}: {row['c']}")

            self.stdout.write(
                "\nNote: Income G/L amounts are often negative (credits). "
                "Compare magnitude to Customer Ledger / invoice totals.\n"
            )

        if schema_name and schema_context:
            with schema_context(schema_name):
                run()
        else:
            run()
