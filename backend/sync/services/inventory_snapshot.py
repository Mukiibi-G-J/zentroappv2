from decimal import Decimal

from django.db.models import Sum

from items.models import Item, ItemLedgerEntries
from sync.models import InventorySnapshot


def get_branch_id_from_request(request):
    from dimension.branch_filter import get_branch_for_request

    branch = get_branch_for_request(request)
    if branch:
        return branch.id
    user = getattr(request, "user", None)
    if user and getattr(user, "global_dimension_1_id", None):
        return user.global_dimension_1_id
    raw = request.META.get("HTTP_X_BRANCH_ID") if request else None
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return None


def item_inventory_for_branch(item, branch_id):
    if branch_id:
        result = ItemLedgerEntries.objects.filter(
            item=item, global_dimension_1_id=branch_id, remaining_quantity__gt=0
        ).aggregate(total=Sum("remaining_quantity"))
        return Decimal(str(result["total"] or 0))
    return Decimal(str(getattr(item, "inventory", 0) or 0))


def rebuild_inventory_snapshots(branch_id=None, item_nos=None):
    """Rebuild denormalized snapshots for a branch (optional item filter)."""
    qs = Item.objects.all()
    if item_nos:
        qs = qs.filter(no__in=item_nos)
    updated = 0
    for item in qs.iterator(chunk_size=200):
        qty = item_inventory_for_branch(item, branch_id)
        InventorySnapshot.objects.update_or_create(
            item_system_id=str(item.system_id),
            branch_id=branch_id,
            defaults={
                "quantity": qty,
                "item_no": item.no or "",
            },
        )
        updated += 1
    return updated


def apply_inventory_deltas_after_post(invoice, branch_id):
    """Refresh snapshots for items on a posted invoice."""
    item_nos = []
    for line in invoice.lines.select_related("item").all():
        if line.item_id:
            item_nos.append(line.item.no)
    if item_nos:
        rebuild_inventory_snapshots(branch_id=branch_id, item_nos=item_nos)
