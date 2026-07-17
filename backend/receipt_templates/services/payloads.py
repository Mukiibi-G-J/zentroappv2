"""Build receipt payloads for receipt report runs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.utils import timezone

from receipt_templates.report_registry import ReceiptReportId


def _decimal_str(value) -> str:
    if value is None:
        return "0"
    return str(value)


def _table_label(order) -> str:
    if order.table_id and order.table:
        tn = getattr(order.table, "table_number", None)
        if tn is not None and str(tn).strip() != "":
            return f"Table {tn}"
        return f"Table #{order.table_id}"
    return "Takeout / Quick sale"


def _waiter_name(order) -> str:
    if not order.waiter_id:
        return ""
    w = order.waiter
    if hasattr(w, "get_full_name"):
        return w.get_full_name() or ""
    return str(getattr(w, "full_name", None) or w)


def build_kot_bar_ticket_payload(
    order,
    item_ids: Optional[list[int]] = None,
    *,
    receipt_type: str = "kot",
    title: Optional[str] = None,
) -> dict[str, Any]:
    from restaurant_management import models as rm

    qs = rm.RestaurantOrderItem.objects.filter(order=order).select_related("item")
    if item_ids:
        qs = qs.filter(id__in=item_ids)
    else:
        qs = qs.exclude(status="cancelled")

    lines = []
    for it in qs.order_by("id"):
        fire_display = ""
        if hasattr(it, "get_fire_state_display"):
            fire_display = it.get_fire_state_display() or ""
        lines.append(
            {
                "itemName": it.item.item_name if it.item else "",
                "quantity": _decimal_str(it.quantity),
                "specialInstructions": (it.special_instructions or "").strip() or None,
                "fireStateDisplay": fire_display or None,
                "seatNo": it.seat_no,
            }
        )

    return {
        "receiptType": receipt_type,
        "title": title or ("KITCHEN ORDER" if receipt_type == "kot" else "BAR ORDER"),
        "orderNo": order.no,
        "tableLabel": _table_label(order),
        "orderTypeDisplay": order.get_order_type_display(),
        "waiterName": _waiter_name(order) or None,
        "printedAt": timezone.now().isoformat(),
        "items": lines,
    }


def build_guest_check_payload(order) -> dict[str, Any]:
    from restaurant_management.enums import OrderItemStatus

    item_qs = order.order_items.exclude(status=OrderItemStatus.CANCELLED).select_related("item")
    lines = []
    total = Decimal("0")
    for it in item_qs:
        line_total = it.total_price if it.total_price is not None else it.quantity * it.unit_price
        total += Decimal(str(line_total or 0))
        lines.append(
            {
                "itemName": it.item.item_name if it.item else "",
                "quantity": _decimal_str(it.quantity),
                "unitPrice": _decimal_str(it.unit_price),
                "totalPrice": _decimal_str(line_total),
            }
        )

    customer_name = ""
    if order.customer_id and order.customer:
        customer_name = getattr(order.customer, "name", "") or ""

    return {
        "receiptType": "interim_bill",
        "orderNo": order.no,
        "tableLabel": _table_label(order),
        "orderTypeDisplay": order.get_order_type_display(),
        "waiterName": _waiter_name(order) or None,
        "documentDate": timezone.now().date().isoformat(),
        "customerName": customer_name or None,
        "lines": lines,
        "totalAmount": float(total),
    }


def build_payment_journal_receipt_payload(journal) -> dict[str, Any]:
    lines = []
    for line in journal.lines.all().order_by("line_no"):
        label = (line.description or "").strip()
        if not label:
            account_type = (line.account_type or "").strip()
            account_no = (line.account_no or "").strip()
            label = " ".join(part for part in (account_type, account_no) if part).strip() or "Payment line"
        lines.append(
            {
                "itemName": label,
                "quantity": "1",
                "unitPrice": _decimal_str(line.amount),
                "totalPrice": _decimal_str(line.amount),
            }
        )

    pm = journal.payment_method
    pm_label = ""
    if pm:
        pm_label = getattr(pm, "description", None) or getattr(pm, "code", None) or str(pm)

    posting_date = journal.posting_date
    if posting_date is None and getattr(journal, "created_at", None):
        posting_date = journal.created_at.date()

    return {
        "receiptType": "payment_journal",
        "documentNo": journal.document_no or "",
        "documentDate": str(posting_date or timezone.now().date()),
        "lines": lines,
        "totalAmount": float(journal.amount or 0),
        "paymentMethod": pm_label or None,
    }


def build_sales_receipt_payload(invoice, *, seller_name: str = "") -> dict[str, Any]:
    lines = []
    for line in invoice.lines.select_related("item", "resource").all():
        name = ""
        if line.item_id and line.item:
            name = line.item.item_name or line.item.no or ""
        elif line.resource_id and line.resource:
            name = getattr(line.resource, "name", "") or ""
        elif line.description:
            name = line.description
        lines.append(
            {
                "itemName": name,
                "quantity": _decimal_str(line.quantity),
                "unitPrice": _decimal_str(line.unit_price),
                "totalPrice": _decimal_str(line.total_amount),
            }
        )

    pm = invoice.payment_method
    pm_label = ""
    if pm:
        pm_label = getattr(pm, "description", None) or getattr(pm, "name", None) or str(pm)

    customer_name = ""
    customer_no = ""
    if invoice.customer_id and invoice.customer:
        customer_name = invoice.customer.name or ""
        customer_no = getattr(invoice.customer, "no", "") or ""

    return {
        "receiptType": "sale",
        "invoiceNo": invoice.invoice_no or "",
        "documentDate": str(invoice.document_date or invoice.created_at.date()),
        "customerName": customer_name,
        "customerNo": customer_no or None,
        "lines": lines,
        "totalAmount": float(invoice.total_amount or 0),
        "vatAmount": float(invoice.total_vat_amount or 0) if invoice.total_vat_amount else None,
        "vatEnabled": bool(invoice.total_vat_amount and invoice.total_vat_amount > 0),
        "amountReceived": float(invoice.amount_received or 0) if invoice.amount_received else None,
        "changeAmount": float(invoice.change_amount or 0) if invoice.change_amount else None,
        "paymentMethod": pm_label or None,
        "sellerName": seller_name or None,
    }


def build_report_payload(report_id: int, request, body: dict) -> dict[str, Any]:
    """Resolve source record(s) and return camelCase payload for the frontend renderer."""
    from sales.models import SalesInvoice

    rid = int(report_id)

    if rid == ReceiptReportId.SALES_RECEIPT:
        system_id = body.get("invoice_system_id") or body.get("system_id")
        if not system_id:
            raise ValueError("invoice_system_id is required")
        invoice = SalesInvoice.objects.prefetch_related("lines__item").select_related(
            "customer", "payment_method"
        ).get(system_id=system_id)
        seller = ""
        if request.user and request.user.is_authenticated:
            seller = (
                request.user.get_full_name()
                if hasattr(request.user, "get_full_name")
                else str(request.user)
            )
        return build_sales_receipt_payload(invoice, seller_name=seller)

    if rid in (ReceiptReportId.KITCHEN_ORDER, ReceiptReportId.BAR_ORDER, ReceiptReportId.GUEST_CHECK):
        from restaurant_management import models as rm

        order_id = body.get("order_id")
        if not order_id:
            raise ValueError("order_id is required")
        order = (
            rm.RestaurantOrder.objects.select_related("table", "waiter", "customer")
            .prefetch_related("order_items__item")
            .get(pk=int(order_id))
        )
        item_ids = body.get("item_ids")
        if item_ids is not None and not isinstance(item_ids, list):
            item_ids = [item_ids]

        if rid == ReceiptReportId.KITCHEN_ORDER:
            return build_kot_bar_ticket_payload(
                order,
                item_ids,
                receipt_type="kot",
                title="KITCHEN ORDER",
            )
        if rid == ReceiptReportId.BAR_ORDER:
            return build_kot_bar_ticket_payload(
                order,
                item_ids,
                receipt_type="bar",
                title="BAR ORDER",
            )
        return build_guest_check_payload(order)

    if rid == ReceiptReportId.PAYMENT_JOURNAL:
        from payments.enums import PaymentStatus
        from payments.models import PaymentJournal

        system_id = body.get("payment_journal_system_id") or body.get("system_id")
        if not system_id:
            raise ValueError("payment_journal_system_id is required")
        journal = (
            PaymentJournal.objects.prefetch_related("lines")
            .select_related("payment_method")
            .get(system_id=system_id)
        )
        if journal.status != PaymentStatus.POSTED.value:
            raise ValueError("Payment must be posted before printing a receipt.")
        return build_payment_journal_receipt_payload(journal)

    raise ValueError(f"Report {report_id} is not implemented yet")
