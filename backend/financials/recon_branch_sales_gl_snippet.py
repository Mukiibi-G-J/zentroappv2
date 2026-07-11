# recon_branch_sales_gl_snippet.py
# From zentro-backend:
#   python manage.py shell
#   exec(open(r"financials/recon_branch_sales_gl_snippet.py", encoding="utf-8").read())
#
# Or one shot:
#   python manage.py shell -c "exec(open(r'financials/recon_branch_sales_gl_snippet.py', encoding='utf-8').read())"

SCHEMA = "primewise"
BRANCH_CODE = "MWANJARI"
SKIP_DOC_BREAKDOWN = False

from django.db.models import Q, Sum, Count
from django_tenants.utils import schema_context

from dimension.models import DimensionValue
from financials.models import GeneralLedgerEntry
from financials.enums import DOCUMENT_TYPE as GL_DOC_TYPE
from sales.models import CustomerLedgerEntry, SalesInvoice


def _run():
    print("\n=== Branch sales vs G/L (Sales posting) ===\n")
    branch = (
        DimensionValue.objects.filter(
            Q(code__iexact=BRANCH_CODE) | Q(description__icontains=BRANCH_CODE)
        )
        .only("id", "code", "description")
        .order_by("id")
        .first()
    )
    if not branch:
        print(f"No DimensionValue matched BRANCH_CODE={BRANCH_CODE!r}")
        return

    print(f"Branch: id={branch.id} code={branch.code!r} description={branch.description!r}\n")

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
    print("Customer Ledger — Invoice rows (not reversed):")
    print(f"  Count: {cle_agg['n'] or 0}")
    print(f"  Sum(amount):  {cle_agg['sum_amount'] or 0}")
    print(f"  Sum(sales):   {cle_agg['sum_sales'] or 0}")

    posted_inv_count = SalesInvoice.objects.filter(
        global_dimension_1_id=branch.id, status="Posted"
    ).count()
    print(f"\nSalesInvoice headers: Posted count = {posted_inv_count}")

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

    print("\nG/L entries — general_posting_type=Sales (not reversed):")
    print(f"  All accounts: count={gl_agg['n_all'] or 0}, Sum(amount)={gl_agg['sum_all'] or 0}")
    print(f"  Income only:  count={gl_agg['n_income'] or 0}, Sum(amount)={gl_agg['sum_income'] or 0}")
    print(f"  Account 6110:  count={gl_agg['n_6110'] or 0}, Sum(amount)={gl_agg['sum_6110'] or 0}")

    print("\n(NULL-branch Sales G/L full-table scan skipped; add in shell if needed.)\n")

    if not SKIP_DOC_BREAKDOWN:
        dt_counts = (
            gl_sales_base.values("document_type").annotate(c=Count("id")).order_by("-c")
        )
        print("Sales G/L rows by document_type:")
        for row in dt_counts[:15]:
            print(f"  {row['document_type']!r}: {row['c']}")

    print(
        "\nNote: Income G/L amounts are often negative (credits). "
        "Compare magnitude to Customer Ledger / invoice totals.\n"
    )


with schema_context(SCHEMA):
    _run()
