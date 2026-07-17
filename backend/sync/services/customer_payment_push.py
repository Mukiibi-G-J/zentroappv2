"""Idempotent sync push handler for POS customer payment events."""

from django.db import transaction
from django.utils import timezone

from payments.quick_customer_payment import (
    QuickCustomerPaymentError,
    quick_customer_payment,
)
from sync.models import SyncEvent


def process_customer_payment_completed(request, device_id, event_id, payload):
    """
    Idempotent CUSTOMER_PAYMENT_COMPLETED: create payment, apply oldest open invoice, post.
    """
    existing = SyncEvent.objects.filter(
        event_id=event_id, status=SyncEvent.STATUS_PROCESSED
    ).first()
    if existing and existing.result:
        cached = dict(existing.result)
        cached.setdefault("ok", True)
        cached["cached"] = True
        return cached

    with transaction.atomic():
        event, _ = SyncEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "device_id": device_id,
                "event_type": "CUSTOMER_PAYMENT_COMPLETED",
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
            result = quick_customer_payment(
                customer_id=payload.get("customer_id"),
                amount=payload.get("amount"),
                payment_method_id=payload.get("payment_method_id"),
                request=request,
            )
            out = {
                "ok": True,
                "local_id": payload.get("local_id"),
                "document_no": result.get("document_no"),
                "system_id": result.get("system_id"),
                "amount": result.get("amount"),
                "customer_id": result.get("customer_id"),
                "customer_no": result.get("customer_no"),
                "customer_name": result.get("customer_name"),
                "applied_document_no": result.get("applied_document_no"),
                "remaining_balance": result.get("remaining_balance"),
            }
            event.status = SyncEvent.STATUS_PROCESSED
            event.result = out
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
            return out
        except QuickCustomerPaymentError as exc:
            event.status = SyncEvent.STATUS_FAILED
            event.error_message = exc.message
            event.save(update_fields=["status", "error_message", "updated_at"])
            raise
        except Exception as exc:
            event.status = SyncEvent.STATUS_FAILED
            event.error_message = str(exc)
            event.save(update_fields=["status", "error_message", "updated_at"])
            raise
