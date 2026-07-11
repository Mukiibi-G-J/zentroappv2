"""
Create an Open SalesInvoice from one or more restaurant orders (shared by
convert-to-invoice and POS counter checkout).
"""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from restaurant_management.enums import OrderItemStatus, OrderStatus


def _production_qty_base_for_restaurant_line(order_item, item_uom) -> Decimal:
    """
    Production order / output journals use base inventory units. Sales posting reduces
    ``line.quantity * item_unit_of_measure.quantity_per_unit`` (see SalesInvoiceProcessor).
    Use the same base quantity so post-output on-hand matches the shipment deduction.
    """
    try:
        line_qty = Decimal(str(order_item.quantity))
    except Exception:
        line_qty = Decimal("1")
    if line_qty <= 0:
        line_qty = Decimal("1")

    per = Decimal("1")
    if item_uom is not None:
        raw = getattr(item_uom, "quantity_per_unit", None)
        if raw is not None and raw != "":
            try:
                per = Decimal(str(raw))
            except Exception:
                per = Decimal("1")
    if per <= 0:
        per = Decimal("1")

    base = (line_qty * per).quantize(Decimal("0.001"))
    return base if base > 0 else Decimal("1")


def _resolve_invoice_header_branch(request, table_orders: list):
    """Branch (Global Dimension 1) for sales invoice header: order context, then request, then defaults."""
    from dimension.branch_filter import get_branch_for_request
    from dimension.utils import get_first_branch_dimension_value

    for ro in table_orders:
        gd = getattr(ro, "global_dimension_1", None)
        if gd is not None:
            return gd
    branch = get_branch_for_request(request) if request else None
    if (
        not branch
        and request
        and getattr(request, "user", None)
        and getattr(request.user, "is_authenticated", False)
    ):
        branch = getattr(request.user, "global_dimension_1", None)
    if not branch:
        branch = get_first_branch_dimension_value()
    return branch


def create_open_sales_invoice_from_restaurant_orders(
    request,
    table_orders: list,
    customer,
    location_to_use,
    *,
    combine_orders: bool = False,
):
    """
    Build invoice lines from restaurant order items, link orders to the invoice,
    and mark restaurant orders completed. Caller must resolve location and customer.
    """
    from dimension.models import get_merged_line_dimensions, get_posting_dimension_payload
    from items.models import ItemUnitOfMeasure
    from production.models import ProductionOrder
    from production.posting import (
        ProductionOrderPostingError,
        ProductionOrderPostingFromPreviewService,
        build_production_posting_preview,
    )
    from sales.models import SalesInvoice, SalesInvoiceLine

    if not table_orders:
        raise ValueError("No restaurant orders to invoice")

    branch = _resolve_invoice_header_branch(request, table_orders)
    dim_payload = get_posting_dimension_payload(global_dimension_1=branch)
    if not dim_payload.get("dimension_set"):
        raise ValueError(
            "Could not resolve posting dimensions for the invoice (dimension set is required). "
            "Check General Ledger Setup (Global Dimension 1) and that branch dimension values exist."
        )

    g1_header = dim_payload["global_dimension_1"] or branch
    if not g1_header:
        raise ValueError(
            "Could not resolve Global Dimension 1 for the invoice header. "
            "Check General Ledger Setup and branch on the restaurant check or user session."
        )

    invoice = SalesInvoice(
        customer=customer,
        contact_person=None,
        document_date=timezone.now().date(),
        posting_date=timezone.now().date(),
        vat_date=timezone.now().date(),
        due_date=timezone.now().date(),
        status="Open",
        dimension_set=dim_payload["dimension_set"],
        global_dimension_1=g1_header,
        global_dimension_2=dim_payload.get("global_dimension_2"),
    )
    invoice.save()

    for restaurant_order in table_orders:
        active_items = restaurant_order.order_items.exclude(
            status=OrderItemStatus.CANCELLED
        )
        for order_item in active_items:
            item_uom = None
            if order_item.item.sales_unit_of_measure:
                item_uom = order_item.item.sales_unit_of_measure
            elif order_item.item.unit_of_measure:
                item_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                    item=order_item.item,
                    unit_of_measure=order_item.item.unit_of_measure,
                    defaults={"quantity_per_unit": 1},
                )

            description = order_item.item.item_name
            if combine_orders and len(table_orders) > 1:
                description = (
                    f"{order_item.item.item_name} (Order: {restaurant_order.no})"
                )

            dims = get_merged_line_dimensions(
                customer_no=getattr(customer, "no", None),
                item=order_item.item,
                request_user=request.user,
                line_data={},
            )
            invoice_line = SalesInvoiceLine.objects.create(
                sales_invoice=invoice,
                item=order_item.item,
                description=description,
                location_code=location_to_use,
                quantity=int(order_item.quantity),
                item_unit_of_measure=item_uom,
                unit_of_measure=order_item.item.unit_of_measure,
                unit_price=float(order_item.unit_price),
                line_discount_amount=0,
                dimension_set=dims.get("dimension_set"),
                global_dimension_1=dims.get("global_dimension_1"),
            )

            if getattr(order_item.item, "production_bom", None):
                try:
                    item_label = (getattr(order_item.item, "item_name", None) or "").strip() or "Item"
                    po_name = f"{item_label} · {restaurant_order.no}"[:100]
                    prod_order = ProductionOrder.objects.create(
                        name=po_name,
                        item=order_item.item,
                        quantity=_production_qty_base_for_restaurant_line(
                            order_item, item_uom
                        ),
                        status="released",
                        source_type="item",
                    )
                    prod_order.refresh_production_details(
                        user=request.user, request=request
                    )

                    preview_data, errors = build_production_posting_preview(
                        prod_order
                    )
                    if errors:
                        raise ProductionOrderPostingError(
                            "; ".join([str(e) for e in errors])
                        )
                    if not preview_data:
                        raise ProductionOrderPostingError(
                            "No posting preview data for production order."
                        )

                    ProductionOrderPostingFromPreviewService(
                        prod_order, request.user, preview_data
                    ).post()
                    prod_order.status = "finished"
                    prod_order.save(update_fields=["status"])
                    prod_order.lines.update(status="completed")
                    prod_order.components.update(status="finished")

                    invoice_line.description = (
                        f"{invoice_line.description} [Prod:{prod_order.no}]"
                    )
                    invoice_line.save(
                        update_fields=["description", "updated_at"]
                    )
                except ProductionOrderPostingError:
                    raise
                except Exception as e:
                    raise ProductionOrderPostingError(str(e)) from e

        restaurant_order.sales_invoice = invoice
        restaurant_order.status = OrderStatus.COMPLETED
        restaurant_order.save(
            update_fields=["sales_invoice", "status", "updated_at"]
        )

    return invoice
