"""Sales price-edit permission helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def _as_money(value) -> Decimal:
    try:
        amount = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")
    return amount.quantize(Decimal("0.01"))


def _catalog_unit_price(item=None, resource=None) -> Decimal | None:
    if item is not None:
        price = getattr(item, "unit_price", None)
        if price is not None and price != "":
            return _as_money(price)
    if resource is not None:
        for attr in ("unit_price", "unit_cost", "price"):
            price = getattr(resource, attr, None)
            if price is not None and price != "":
                return _as_money(price)
    return None


def validate_sales_line_unit_price(
    user,
    *,
    unit_price,
    item=None,
    resource=None,
    line_label: str = "line",
) -> Decimal:
    """
    Enforce company Sales setup + User Setup rules for unit price overrides.

    - Catalog price (matching item/resource card) is always allowed.
    - Overrides require user can_edit_sales_price and company not disable_price_editing.
    - prevent_price_below_original blocks prices below the catalog price.
    """
    from authentication.models import UserSetup
    from sales.models import SalesReceivable

    requested = _as_money(unit_price)
    catalog = _catalog_unit_price(item=item, resource=resource)

    if catalog is not None and requested == catalog:
        return requested

    sales_setup = SalesReceivable.objects.first()
    disable_editing = bool(
        sales_setup and getattr(sales_setup, "disable_price_editing", False)
    )
    prevent_below = bool(
        sales_setup and getattr(sales_setup, "prevent_price_below_original", False)
    )

    user_setup = UserSetup.get_or_create_for_user(user) if user else None
    can_edit = bool(user_setup and user_setup.can_edit_sales_price)

    if disable_editing or not can_edit:
        if catalog is None:
            return requested
        raise ValidationError(
            {
                "unit_price": (
                    f"You do not have permission to edit the sales price on {line_label}. "
                    f"Expected {catalog}."
                )
            }
        )

    if prevent_below and catalog is not None and requested < catalog:
        raise ValidationError(
            {
                "unit_price": (
                    f"Cannot set price below original price on {line_label}. "
                    f"Original price: {catalog}."
                )
            }
        )

    return requested
