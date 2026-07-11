"""
Business Central–aligned Value Entry quantity/cost signs.

BC rule: item ledger quantity, valued quantity, invoiced quantity, and cost amount
share the same direction for a movement:
  - Stock in (Purchase, Positive Adjustment, Output): positive qty and positive cost
  - Stock out (Sales, Negative Adjustment, Direct Cost/COGS, Consumption): negative qty and cost

Item ledger entries for adjustments are often already signed; never apply a second negation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from items.enums import DocumentType, EntryType

# Match reports.services.inventory_value_movement_service ENTRY_TYPE_CATEGORY
STOCK_IN_ENTRY_TYPES = frozenset(
    {
        EntryType.Purchase.name,
        EntryType.Purchase.value,
        EntryType.PositiveAdjustment.name,
        EntryType.PositiveAdjustment.value,
        EntryType.Output.name,
        EntryType.Output.value,
        "Purchase",
        "PositiveAdjustment",
    }
)

STOCK_OUT_ENTRY_TYPES = frozenset(
    {
        EntryType.Sales.name,
        EntryType.Sales.value,
        EntryType.NegativeAdjustment.name,
        EntryType.NegativeAdjustment.value,
        EntryType.DirectCost.name,
        EntryType.DirectCost.value,
        EntryType.Consumption.name,
        EntryType.Consumption.value,
        "Sales",
        "NegativeAdjustment",
        "DirectCost",
        "Purchase Return",
    }
)


def resolve_inventory_entry_type(
    entry_type: str | None,
    document_type: str | None = None,
) -> str | None:
    """
    Map legacy/mis-posted types for inventory movement (BC-aligned).

    Purchase invoices were sometimes stored as Direct Cost; treat as Purchase
    when document_type is a purchase receipt/invoice.
    """
    et = (entry_type or "").strip()
    doc = (document_type or "").strip()
    if et in (
        EntryType.DirectCost.name,
        EntryType.DirectCost.value,
        "DirectCost",
    ):
        doc_lower = doc.lower()
        if "credit" in doc_lower or "return" in doc_lower:
            return "Purchase Return"
        if doc in (
            EntryType.Purchase.value,
            EntryType.Purchase.name,
            DocumentType.Purchase.value,
            DocumentType.PurchaseReceipt.value,
            "Purchase",
            "Purchase Receipt",
        ):
            return EntryType.Purchase.value
    return et or None


def parse_cost_amount(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except Exception:
        return Decimal("0")


def normalize_cost_per_unit(
    cost_per_unit=None,
    *,
    cost_abs: Decimal | None = None,
    qty_abs: int = 0,
) -> float:
    """Preserve fractional unit costs (e.g. 1791.67); round to 2 dp for storage."""
    if cost_per_unit is not None and str(cost_per_unit).strip() != "":
        try:
            return round(float(str(cost_per_unit).strip().replace(",", "")), 2)
        except (TypeError, ValueError):
            pass
    if qty_abs and cost_abs is not None:
        return round(float(cost_abs / qty_abs), 2)
    return 0.0


def entry_type_stock_direction(
    entry_type: str | None,
    document_type: str | None = None,
) -> str | None:
    """Return 'in', 'out', or None if unknown."""
    et = resolve_inventory_entry_type(entry_type, document_type) or ""
    et = (et or "").strip()
    if et in STOCK_IN_ENTRY_TYPES:
        return "in"
    if et in STOCK_OUT_ENTRY_TYPES:
        return "out"
    return None


def bc_normalize_value_entry_fields(
    entry_type: str | None,
    quantity,
    cost_amount,
    *,
    cost_per_unit=None,
) -> dict[str, Any]:
    """
    Normalize qty and cost for a Value Entry row (BC-style).

    Returns keys: item_ledger_entry_quantity, invoiced_quantity, valued_quantity,
    cost_amount (str), cost_per_unit (float).
    """
    direction = entry_type_stock_direction(entry_type, None)
    qty_raw = int(quantity or 0)
    cost_raw = parse_cost_amount(cost_amount)
    qty_abs = abs(qty_raw)
    cost_abs = abs(cost_raw)

    if direction == "in":
        qty_signed = qty_abs
        cost_signed = cost_abs
    elif direction == "out":
        qty_signed = -qty_abs if qty_abs else 0
        cost_signed = -cost_abs if cost_abs else Decimal("0")
    else:
        qty_signed = qty_raw
        cost_signed = cost_raw

    cpu = normalize_cost_per_unit(
        cost_per_unit,
        cost_abs=cost_abs,
        qty_abs=qty_abs,
    )

    if cost_signed == cost_signed.to_integral_value():
        cost_str = str(int(cost_signed))
    else:
        cost_str = str(cost_signed)

    return {
        "item_ledger_entry_quantity": qty_signed,
        "invoiced_quantity": qty_signed,
        "valued_quantity": qty_signed,
        "cost_amount": cost_str,
        "cost_per_unit": cpu,
    }


def apply_bc_signs_to_value_entry_instance(entry) -> bool:
    """
    Mutate a ValueEntry model instance in place. Returns True if any field changed.
    """
    if getattr(entry, "reversed", False):
        return False

    normalized = bc_normalize_value_entry_fields(
        entry.entry_type,
        entry.item_ledger_entry_quantity,
        entry.cost_amount,
        cost_per_unit=entry.cost_per_unit,
    )
    changed = False
    for field, new_val in normalized.items():
        if getattr(entry, field) != new_val:
            setattr(entry, field, new_val)
            changed = True
    return changed
