from django.utils import timezone

from financials.models import PaymentMethod
from financials.serializers import PaymentMethodSerializer
from items.models import Item
from items.serializers import ItemSerializer
from sales.models import Customer
from sync.serializers import CustomerSyncSerializer
from sales.setup_data import fetch_company_info_data, fetch_sales_setup_data
from sync.services.inventory_snapshot import get_branch_id_from_request


def build_bootstrap_payload(request, device_id=None):
    """Full catalog bundle for initial / branch-scoped sync."""
    branch_id = get_branch_id_from_request(request)
    items_qs = Item.objects.all().order_by("item_name")[:5000]
    items_data = ItemSerializer(
        items_qs, many=True, context={"request": request}
    ).data

    customers_qs = Customer.objects.all().order_by("name")[:5000]
    customers_data = CustomerSyncSerializer(customers_qs, many=True).data

    payment_methods = PaymentMethodSerializer(
        PaymentMethod.objects.all(), many=True
    ).data

    company_info = fetch_company_info_data(request)
    sales_setup = fetch_sales_setup_data()

    item_on_hand = []
    for row in items_data:
        inv = row.get("inventory") or 0
        if row.get("system_id"):
            item_on_hand.append(
                {
                    "item_system_id": str(row["system_id"]),
                    "item_no": row.get("no"),
                    "branch_id": branch_id,
                    "quantity": inv,
                }
            )

    return {
        "device_id": device_id,
        "branch_id": branch_id,
        "server_time": timezone.now().isoformat(),
        "cursor": timezone.now().isoformat(),
        "items": items_data,
        "customers": customers_data,
        "payment_methods": payment_methods,
        "item_on_hand": item_on_hand,
        "company_info": company_info,
        "sales_setup": sales_setup,
    }
