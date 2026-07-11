"""Shared rules for when a restaurant check/order must not be edited."""

from __future__ import annotations

from .enums import OrderStatus

CLOSED_ORDER_ERROR = "This check is closed and cannot be modified."


def order_is_closed(order) -> bool:
    """Paid or completed checks are immutable (cancelled unpaid checks can be reopened)."""
    if order is None:
        return False
    if getattr(order, "sales_invoice_id", None):
        return True
    status = getattr(order, "status", None)
    if status == OrderStatus.COMPLETED:
        return True
    return False
