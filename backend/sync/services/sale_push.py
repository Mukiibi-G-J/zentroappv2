import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.admin import SalesInvoiceAdmin
from sales.models import Customer, SalesInvoice
from sales.serializers import SalesInvoiceSerializer
from sales.views import SalesInvoicePostingProcessor
from sync.models import SyncEvent
from sync.services.inventory_snapshot import (
    apply_inventory_deltas_after_post,
    get_branch_id_from_request,
)


def _resolve_customer(payload):
    customer_id = payload.get("customer")
    customer_name = (payload.get("customer_name") or "").strip()
    if customer_id:
        try:
            return Customer.objects.filter(pk=customer_id).first()
        except (TypeError, ValueError):
            pass
    if customer_name:
        customer = Customer.objects.filter(name__iexact=customer_name).first()
        if customer:
            return customer
    walk_in = Customer.objects.filter(name__icontains="walk").first()
    if walk_in:
        return walk_in
    return Customer.objects.order_by("id").first()


def _build_invoice_data(payload, customer):
    lines = payload.get("lines") or []
    invoice_data = {
        "system_id": payload.get("system_id") or str(uuid.uuid4()),
        "customer": customer.pk if customer else None,
        "customer_name": customer.name if customer else payload.get("customer_name"),
        "document_date": payload.get("document_date") or timezone.now().date().isoformat(),
        "status": "Open",
        "amount_received": payload.get("amount_received", 0),
        "change_amount": payload.get("change_amount", 0),
        "payment_method": payload.get("payment_method"),
        "invoice_discount_type": payload.get("invoice_discount_type"),
        "invoice_discount_amount": str(payload.get("invoice_discount_amount") or "0"),
        "invoice_discount_percentage": str(
            payload.get("invoice_discount_percentage") or "0"
        ),
        "lines": lines,
    }
    return invoice_data


def _post_invoice_internal(invoice, request):
    mock_admin = SalesInvoiceAdmin(SalesInvoice, None)
    can_post, reason = mock_admin.can_post_invoice(invoice)
    if not can_post:
        raise ValidationError(reason or "Cannot post invoice")

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )
    processor = SalesInvoicePostingProcessor(invoice, request, receipt_no)
    result = processor.post()
    if not result.get("success"):
        raise ValidationError(result.get("message") or "Posting failed")
    invoice.refresh_from_db()
    return invoice


def process_sale_completed(request, device_id, event_id, payload):
    """
    Idempotent SALE_COMPLETED: upsert Open invoice, lines via serializer, post.
    Returns dict for API response.
    """
    existing = SyncEvent.objects.filter(
        event_id=event_id, status=SyncEvent.STATUS_PROCESSED
    ).first()
    if existing and existing.result:
        cached = dict(existing.result)
        cached.setdefault("ok", True)
        cached["cached"] = True
        return cached

    branch_id = get_branch_id_from_request(request)
    customer = _resolve_customer(payload)
    if not customer:
        raise ValidationError("Customer is required for sale sync")

    invoice_data = _build_invoice_data(payload, customer)
    system_id = invoice_data["system_id"]

    with transaction.atomic():
        event, _ = SyncEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "device_id": device_id,
                "event_type": "SALE_COMPLETED",
                "payload": payload,
                "status": SyncEvent.STATUS_PROCESSING,
            },
        )
        if event.status == SyncEvent.STATUS_PROCESSED and event.result:
            return {"ok": True, "cached": True, **event.result}

        event.status = SyncEvent.STATUS_PROCESSING
        event.payload = payload
        event.save(update_fields=["status", "payload", "updated_at"])

        try:
            sale = SalesInvoice.objects.filter(system_id=system_id).first()
            serializer = SalesInvoiceSerializer(
                sale,
                data=invoice_data,
                partial=bool(sale),
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            sale = serializer.save()

            if sale.status == "Posted":
                result = {
                    "ok": True,
                    "server_sale_id": sale.id,
                    "system_id": str(sale.system_id),
                    "invoice_no": sale.invoice_no,
                    "status": sale.status,
                }
            else:
                sale = _post_invoice_internal(sale, request)
                apply_inventory_deltas_after_post(sale, branch_id)
                result = {
                    "ok": True,
                    "server_sale_id": sale.id,
                    "system_id": str(sale.system_id),
                    "invoice_no": sale.invoice_no,
                    "status": sale.status,
                    "local_id": payload.get("local_id"),
                    "total_amount": float(
                        sum(
                            Decimal(str(line.total_amount))
                            for line in sale.lines.all()
                        )
                    ),
                }

            event.status = SyncEvent.STATUS_PROCESSED
            event.result = result
            event.processed_at = timezone.now()
            event.error_message = ""
            event.save(
                update_fields=[
                    "status",
                    "result",
                    "processed_at",
                    "error_message",
                    "updated_at",
                ]
            )
            return result
        except Exception as exc:
            event.status = SyncEvent.STATUS_FAILED
            event.error_message = str(exc)
            event.save(update_fields=["status", "error_message", "updated_at"])
            raise
