from django.shortcuts import render
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django.db.models import Q
from reports.utils.formatters import format_currency

# Import models from different apps
from items.models import Item
from sales.models import SalesInvoice, Customer
from purchases.models import PurchaseInvoice, Vendor
from financials.models import G_LAccount, GeneralLedgerEntry
from payments.models import PaymentJournal
from company.models import Company

# Activity/notification models
from expenses.models import Expense

# Create your views here.


def _schema_from_request(request) -> str | None:
    """Extract tenant schema from JWT (same pattern as pages views)."""
    auth = getattr(request, "auth", None)
    if auth is None:
        return None
    try:
        return auth.get("schema_name") or auth["schema_name"]
    except (KeyError, AttributeError, TypeError):
        return None


def _record_search_result(
    *,
    title,
    description,
    icon,
    category,
    category_title,
    page_name,
    system_id,
    url="",
):
    """Build a global-search row with V2 page-engine navigation metadata."""
    return {
        "title": title,
        "description": description,
        "icon": icon,
        "category": category,
        "categoryTitle": category_title,
        "pageName": page_name,
        "systemId": str(system_id),
        "url": url,
    }


def _run_global_search(request, query: str):
    """Execute cross-module search against the current tenant schema."""
    search_results = []

    # Search in Items (Inventory Management)
    items = Item.objects.filter(
        Q(item_name__icontains=query)
        | Q(bar_code_no__icontains=query)
        | Q(no__icontains=query)
    )[:5]

    if items.exists():
        search_results.append(
            {
                "title": "Inventory",
                "data": [
                    _record_search_result(
                        title=item.item_name,
                        description=f"Item #{item.no} - {item.item_name}",
                        icon="items",
                        category="Inventory",
                        category_title="Inventory Management",
                        page_name="ItemCard",
                        system_id=item.system_id,
                        url=f"/items/{item.no}/",
                    )
                    for item in items
                ],
            }
        )

    # Search in Sales Invoices
    sales_invoices = SalesInvoice.objects.filter(
        Q(invoice_no__icontains=query) | Q(customer__name__icontains=query)
    )[:5]

    if sales_invoices.exists():
        search_results.append(
            {
                "title": "Sales",
                "data": [
                    _record_search_result(
                        title=f"Invoice {invoice.invoice_no}",
                        description=f'Customer: {invoice.customer.name if invoice.customer else "N/A"}',
                        icon="sales",
                        category="Sales",
                        category_title="Sales Management",
                        page_name="SalesInvoice",
                        system_id=invoice.system_id,
                        url=f"/sales/invoice/{invoice.id}/",
                    )
                    for invoice in sales_invoices
                ],
            }
        )

    # Search in Customers
    customers = Customer.objects.filter(
        Q(name__icontains=query) | Q(no__icontains=query)
    )[:5]

    if customers.exists():
        search_results.append(
            {
                "title": "Customers",
                "data": [
                    _record_search_result(
                        title=customer.name,
                        description=f"Customer #{customer.no}",
                        icon="sales",
                        category="Sales",
                        category_title="Sales Management",
                        page_name="CustomerCard",
                        system_id=customer.system_id,
                        url=f"/sales/customers/{customer.id}/",
                    )
                    for customer in customers
                ],
            }
        )

    # Search in Purchase Invoices
    purchase_invoices = PurchaseInvoice.objects.filter(
        Q(invoice_no__icontains=query) | Q(vendor__name__icontains=query)
    )[:5]

    if purchase_invoices.exists():
        search_results.append(
            {
                "title": "Purchases",
                "data": [
                    _record_search_result(
                        title=f"Purchase Invoice {invoice.invoice_no}",
                        description=f'Vendor: {invoice.vendor.name if invoice.vendor else "N/A"}',
                        icon="purchases",
                        category="Purchases",
                        category_title="Purchase Management",
                        page_name="PurchaseInvoice",
                        system_id=invoice.system_id,
                        url=f"/purchases/invoice/{invoice.id}/",
                    )
                    for invoice in purchase_invoices
                ],
            }
        )

    # Search in Vendors
    vendors = Vendor.objects.filter(
        Q(name__icontains=query) | Q(no__icontains=query)
    )[:5]

    if vendors.exists():
        search_results.append(
            {
                "title": "Vendors",
                "data": [
                    _record_search_result(
                        title=vendor.name,
                        description=f"Vendor #{vendor.no}",
                        icon="purchases",
                        category="Purchases",
                        category_title="Purchase Management",
                        page_name="VendorCard",
                        system_id=vendor.system_id,
                        url=f"/purchases/vendors/{vendor.id}/",
                    )
                    for vendor in vendors
                ],
            }
        )

    # Search in GL Accounts (Financials)
    gl_accounts = G_LAccount.objects.filter(
        Q(name__icontains=query) | Q(no__icontains=query)
    )[:5]

    if gl_accounts.exists():
        search_results.append(
            {
                "title": "Financials",
                "data": [
                    _record_search_result(
                        title=account.name,
                        description=f"Account #{account.no} - {account.accounttype}",
                        icon="financials",
                        category="Financials",
                        category_title="Financial Management",
                        page_name="GLAccountCard",
                        system_id=account.system_id,
                        url=f"/financials/chart-of-accounts?account={account.no}",
                    )
                    for account in gl_accounts
                ],
            }
        )

    # Search in Payments
    payments = PaymentJournal.objects.filter(
        Q(document_no__icontains=query) | Q(description__icontains=query)
    )[:5]

    if payments.exists():
        search_results.append(
            {
                "title": "Payments",
                "data": [
                    _record_search_result(
                        title=f"Payment {payment.document_no}",
                        description=payment.description or "Payment transaction",
                        icon="payments",
                        category="Payments",
                        category_title="Payment Management",
                        page_name="PaymentJournalCard",
                        system_id=payment.system_id,
                        url=f"/payments/{payment.id}/",
                    )
                    for payment in payments
                ],
            }
        )

    # Search in Item Journals (inventory adjustment + opening balance)
    from items.models import ItemJournal
    from dimension.branch_filter import filter_queryset_by_branch

    item_journals = (
        ItemJournal.objects.filter(
            Q(document_no__icontains=query)
            | Q(description__icontains=query)
            | Q(item__item_name__icontains=query)
            | Q(item__no__icontains=query)
        )
        .filter(
            Q(journal_template__type="item") | Q(journal_template__isnull=True)
        )
        .select_related("item")
        .order_by("-date", "-created_at")
    )
    item_journals = filter_queryset_by_branch(
        item_journals, request.user, ItemJournal, request=request,
    )[:5]

    if item_journals.exists():
        search_results.append(
            {
                "title": "Item Journals",
                "data": [
                    _record_search_result(
                        title=journal.document_no,
                        description=(
                            f"{journal.get_entry_type_display()} — "
                            f"{journal.item.item_name if journal.item else 'N/A'}"
                            + (
                                f" ({journal.adjustment_type.replace('_', ' ').title()})"
                                if journal.adjustment_type
                                else ""
                            )
                        ),
                        icon="items",
                        category="Inventory",
                        category_title="Inventory Management",
                        page_name="ItemJournalCard",
                        system_id=journal.system_id,
                    )
                    for journal in item_journals
                ],
            }
        )

    return search_results


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def global_search(request):
    """
    Global search endpoint that searches across multiple models in the ZentroApp system.

    Works from the public host (e.g. localhost:8002) by switching to the tenant
    schema from the JWT `schema_name` claim — same approach as the page engine.
    """
    query = request.data.get("query", "").strip()

    if not query:
        return Response(
            {"error": "Query parameter is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    schema = _schema_from_request(request)
    if not schema:
        return Response(
            {"error": "No tenant in token"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with schema_context(schema):
            search_results = _run_global_search(request, query)
        return Response({"data": search_results})

    except Exception as e:
        return Response(
            {"error": f"Search failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _format_relative_date(dt):
    """Format datetime as relative string (e.g. '5 min ago', 'Yesterday')"""
    if not dt:
        return ""
    now = timezone.now()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins} min ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 172800:  # < 2 days
        return "Yesterday"
    elif seconds < 604800:  # < 7 days
        days = int(seconds / 86400)
        return f"{days} days ago"
    else:
        return dt.strftime("%b %d, %Y")


def _build_activity_item(
    id_str,
    target,
    description,
    date_str,
    activity_type,
    location,
    location_label,
    status="succeed",
    readed=True,
):
    """Build activity item in format expected by Notification component"""
    return {
        "id": id_str,
        "target": target,
        "description": description,
        "date": date_str,
        "image": "",
        "type": activity_type,
        "location": location,
        "locationLabel": location_label,
        "status": status,
        "readed": readed,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def activity_recent(request):
    """
    Return recent activity for the notification dropdown.
    Aggregates recent sales, payments, and expenses.
    """
    limit = 10
    activities_with_ts = []

    try:
        # 1. Recent Posted Sales
        sales = (
            SalesInvoice.objects.filter(status="Posted")
            .select_related("customer")
            .order_by("-created_at")[:limit]
        )
        for sale in sales:
            total = sum(
                float(line.quantity or 0) * float(line.unit_price or 0)
                for line in sale.lines.all()
            )
            item = _build_activity_item(
                id_str=f"sale-{sale.id}",
                target=sale.invoice_no or f"INV-{sale.id}",
                description=f"Sale for {format_currency(int(total))} posted",
                date_str=_format_relative_date(sale.created_at),
                activity_type=0,
                location="/app/sales/sales-history",
                location_label="View sales",
            )
            activities_with_ts.append((sale.created_at, item))

        # 2. Recent Posted Payments (PaymentJournal)
        payments = PaymentJournal.objects.filter(
            status="Posted"
        ).order_by("-created_at")[:limit]
        for pmt in payments:
            amount = pmt.amount or 0
            item = _build_activity_item(
                id_str=f"payment-{pmt.id}",
                target=pmt.document_no or f"PAY-{pmt.id}",
                description=f"Payment of {format_currency(amount)} received",
                date_str=_format_relative_date(pmt.created_at),
                activity_type=2,
                location="/app/payments",
                location_label="View payments",
                status="succeed",
            )
            activities_with_ts.append((pmt.created_at, item))

        # 3. Recent Posted Expenses
        expenses = (
            Expense.objects.filter(status="Posted")
            .select_related("expense_type")
            .order_by("-created_at")[:limit]
        )
        for exp in expenses:
            amount = exp.amount or 0
            item = _build_activity_item(
                id_str=f"expense-{exp.id}",
                target=exp.document_no or f"EXP-{exp.id}",
                description=f"Expense of {format_currency(amount)} posted",
                date_str=_format_relative_date(exp.created_at),
                activity_type=0,
                location="/app/expenses/expense-history",
                location_label="View expense history",
            )
            activities_with_ts.append((exp.created_at, item))

        # Sort by created_at descending and take top limit
        def _sort_key(x):
            ts = x[0]
            return ts.timestamp() if ts else 0

        activities_with_ts.sort(key=_sort_key, reverse=True)
        activities = [item for _, item in activities_with_ts[:limit]]

        return Response(activities)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def activity_count(request):
    """
    Return unread activity count. Phase 1: always returns 0.
    Phase 3 can add last_read_at tracking.
    """
    return Response({"count": 0})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def activity_list(request):
    """
    Paginated activity list for View All Activity page.
    """
    from django.core.paginator import Paginator

    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 20)), 50)
    activity_type_filter = request.query_params.get("type", "")

    activities = []

    try:
        # 1. Sales
        if not activity_type_filter or activity_type_filter == "sales":
            sales = (
                SalesInvoice.objects.filter(status="Posted")
                .select_related("customer")
                .order_by("-created_at")[:100]
            )
            for sale in sales:
                total = sum(
                    float(line.quantity or 0) * float(line.unit_price or 0)
                    for line in sale.lines.all()
                )
                activities.append(
                    {
                        **_build_activity_item(
                            id_str=f"sale-{sale.id}",
                            target=sale.invoice_no or f"INV-{sale.id}",
                            description=f"Sale for {format_currency(int(total))} posted",
                            date_str=_format_relative_date(sale.created_at),
                            activity_type=0,
                            location=f"/app/sales/sales-history-detail/{sale.id}",
                            location_label="View invoice",
                        ),
                        "source": "sale",
                        "created_at": sale.created_at.isoformat()
                        if sale.created_at
                        else None,
                    }
                )

        # 2. Payments
        if not activity_type_filter or activity_type_filter == "payments":
            payments = PaymentJournal.objects.filter(
                status="Posted"
            ).order_by("-created_at")[:100]
            for pmt in payments:
                amount = pmt.amount or 0
                activities.append(
                    {
                        **_build_activity_item(
                            id_str=f"payment-{pmt.id}",
                            target=pmt.document_no or f"PAY-{pmt.id}",
                            description=f"Payment of {format_currency(amount)} received",
                            date_str=_format_relative_date(pmt.created_at),
                            activity_type=2,
                            location="/app/payments",
                            location_label="View payments",
                            status="succeed",
                        ),
                        "source": "payment",
                        "created_at": pmt.created_at.isoformat()
                        if pmt.created_at
                        else None,
                    }
                )

        # 3. Expenses
        if not activity_type_filter or activity_type_filter == "expenses":
            expenses = (
                Expense.objects.filter(status="Posted")
                .select_related("expense_type")
                .order_by("-created_at")[:100]
            )
            for exp in expenses:
                amount = exp.amount or 0
                activities.append(
                    {
                        **_build_activity_item(
                            id_str=f"expense-{exp.id}",
                            target=exp.document_no or f"EXP-{exp.id}",
                            description=f"Expense of {format_currency(amount)} posted",
                            date_str=_format_relative_date(exp.created_at),
                            activity_type=0,
                            location="/app/expenses/expense-history",
                            location_label="View expense history",
                        ),
                        "source": "expense",
                        "created_at": exp.created_at.isoformat()
                        if exp.created_at
                        else None,
                    }
                )

        # Sort by created_at descending
        activities.sort(
            key=lambda a: a.get("created_at") or "",
            reverse=True,
        )

        paginator = Paginator(activities, page_size)
        page_obj = paginator.get_page(page)
        results = list(page_obj.object_list)
        for r in results:
            r.pop("created_at", None)

        return Response(
            {
                "results": results,
                "count": paginator.count,
                "page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
            }
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
