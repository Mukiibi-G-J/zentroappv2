"""Mirror public company billing/subscription data into tenant setup tables for page engine."""

from __future__ import annotations

from django.utils import timezone
from django_tenants.utils import schema_context


def _public_company():
    from setup.models import CompanyInformation

    return CompanyInformation._resolve_public_company()


def sync_company_subscription():
    from company.models import Subscription
    from company.subscription_grace import period_end_date, payment_due_date
    from setup.models import CompanySubscription

    company = _public_company()
    if company is None:
        return None

    with schema_context('public'):
        sub = Subscription.objects.filter(company=company).first()

    obj = CompanySubscription.objects.first()
    if obj is None:
        obj = CompanySubscription()

    if sub is None:
        obj.plan = ''
        obj.status = 'none'
        obj.billing_cycle = ''
        obj.is_active = False
        obj.in_grace_period = False
        obj.days_remaining = 0
        obj.grace_days_remaining = 0
        obj.is_paid = False
        obj.period_end_date = None
        obj.payment_due_date = None
        obj.subscription_end_date = None
        obj.access_lock_date = None
        obj.save()
        return obj

    today = timezone.now().date()
    period_end = period_end_date(sub)
    due = payment_due_date(sub)
    lock = sub.access_lock_date()
    in_grace = sub.is_in_grace_period()
    days_remaining = max(0, (period_end - today).days) if period_end else 0
    grace_days = max(0, (lock - today).days) if in_grace and lock else 0

    obj.plan = sub.plan or ''
    obj.status = sub.status or ''
    obj.billing_cycle = sub.billing_cycle or ''
    obj.is_active = sub.is_active()
    obj.in_grace_period = in_grace
    obj.is_paid = sub.is_paid
    obj.days_remaining = days_remaining
    obj.grace_days_remaining = grace_days
    obj.period_end_date = period_end
    obj.payment_due_date = due
    obj.subscription_end_date = sub.subscription_end_date
    obj.access_lock_date = lock
    obj.save()
    return obj


def sync_company_billing_history():
    from company.models import BillingHistory
    from setup.models import CompanyBillingHistory

    company = _public_company()
    if company is None:
        return 0

    with schema_context('public'):
        rows = list(
            BillingHistory.objects.filter(company=company).order_by('-billing_date')[:100],
        )

    seen_public_ids: set[int] = set()
    for row in rows:
        seen_public_ids.add(row.id)
        CompanyBillingHistory.objects.update_or_create(
            public_id=row.id,
            defaults={
                'reference_number': row.reference_number,
                'product': row.product,
                'status': row.status,
                'billing_date': row.billing_date,
                'amount': row.amount,
                'currency': row.currency,
            },
        )

    if seen_public_ids:
        CompanyBillingHistory.objects.exclude(public_id__in=seen_public_ids).delete()
    else:
        CompanyBillingHistory.objects.all().delete()

    return len(seen_public_ids)


def sync_company_payment_methods():
    from company.models import PaymentMethod
    from setup.models import CompanyPaymentMethod

    company = _public_company()
    if company is None:
        return 0

    with schema_context('public'):
        rows = list(
            PaymentMethod.objects.filter(company=company, is_active=True).order_by('-is_primary', 'id'),
        )

    seen_public_ids: set[int] = set()
    for row in rows:
        seen_public_ids.add(row.id)
        CompanyPaymentMethod.objects.update_or_create(
            public_id=row.id,
            defaults={
                'method_type': row.method_type,
                'holder_name': row.holder_name,
                'last_four_digits': row.last_four_digits or '',
                'is_primary': row.is_primary,
                'is_active': row.is_active,
            },
        )

    if seen_public_ids:
        CompanyPaymentMethod.objects.exclude(public_id__in=seen_public_ids).delete()
    else:
        CompanyPaymentMethod.objects.all().delete()

    return len(seen_public_ids)
