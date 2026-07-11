"""
Subscription grace period: payment due date, access lock date, trial vs paid messaging.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from company.models import Company, Subscription

DEFAULT_GRACE_DAYS = 2


def grace_days_for_company(company: Any) -> int:
    if company is None:
        return DEFAULT_GRACE_DAYS
    g = getattr(company, "subscription_grace_days", None)
    if g is None:
        return DEFAULT_GRACE_DAYS
    try:
        n = int(g)
    except (TypeError, ValueError):
        return DEFAULT_GRACE_DAYS
    return max(0, n)


def period_end_date(subscription: Subscription) -> date | None:
    """Last inclusive day of the current trial or paid period."""
    from company.enums import SubscriptionStatus

    if subscription.status == SubscriptionStatus.TRIAL.value:
        return subscription.trial_period_end_date
    return subscription.subscription_end_date


def payment_due_date(subscription: Subscription) -> date | None:
    """First calendar day payment is due (day after period end)."""
    end = period_end_date(subscription)
    if end is None:
        return None
    return end + timedelta(days=1)


def access_lock_date_for(subscription: Subscription, company: Company | None = None) -> date | None:
    """
    First calendar day tenant APIs return 402 (inclusive lock).
    Full access for today < lock_date.
    """
    due = payment_due_date(subscription)
    if due is None:
        return None
    co = company if company is not None else getattr(subscription, "company", None)
    gd = grace_days_for_company(co)
    return due + timedelta(days=gd)


def in_grace_period(
    today: date,
    subscription: Subscription,
    company: Company | None = None,
) -> bool:
    """True if past period end but before access lock (exclusive of lock day)."""
    end = period_end_date(subscription)
    lock = access_lock_date_for(subscription, company)
    if end is None or lock is None:
        return False
    return end < today < lock


def reminder_offsets_for_company(company: Any) -> list[int]:
    """
    Days after due_date on which to send grace reminders.
    Default: 0 .. grace_days-1 inclusive.
    """
    raw = getattr(company, "grace_reminder_offsets", None)
    grace = grace_days_for_company(company)
    if grace <= 0:
        return []
    if raw is None:
        return list(range(grace))
    if not isinstance(raw, list):
        return list(range(grace))
    out: list[int] = []
    for x in raw:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 0 <= n < grace:
            out.append(n)
    return sorted(set(out)) if out else list(range(grace))


def expiry_kind_for_subscription(subscription: Subscription) -> str:
    """Return 'trial' or 'subscription' for API / UI copy after access lock."""
    from company.enums import SubscriptionStatus

    if (
        subscription.status == SubscriptionStatus.TRIAL.value
        and not subscription.is_paid
    ):
        return "trial"
    return "subscription"


def expiry_detail_for_kind(kind: str) -> str:
    if kind == "trial":
        return "Your trial has ended. Please subscribe to continue using Zentro."
    return (
        "Your subscription payment is overdue. Please renew to restore full access."
    )
