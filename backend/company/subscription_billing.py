"""
Calendar-based subscription period math (billing anchor on payment day).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Mapping

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from company.enums import SubscriptionPlan


def parse_billing_period_from_metadata(metadata: Mapping[str, Any] | None) -> tuple[int, str]:
    """Return (months, billing_cycle) with billing_cycle in monthly|yearly."""
    meta = dict(metadata or {})
    raw_months = meta.get("months")
    try:
        months = int(raw_months) if raw_months is not None else 1
    except (TypeError, ValueError):
        months = 1
    months = max(1, months)
    bc = str(meta.get("billing_cycle") or "monthly").strip().lower()
    if bc not in ("monthly", "yearly"):
        bc = "monthly"
    return months, bc


def relativedelta_for_billing(months: int, billing_cycle: str) -> relativedelta:
    """Advance by whole calendar months or years (yearly uses months as year count)."""
    months = max(1, int(months))
    cycle = (billing_cycle or "monthly").strip().lower()
    if cycle == "yearly":
        return relativedelta(years=months)
    return relativedelta(months=months)


def subscription_period_end_inclusive(
    payment_date: date, months: int, billing_cycle: str
) -> date:
    """
    Last inclusive day of access: the day before the next billing anchor.
    e.g. pay Jan 10 monthly x1 -> anchor Feb 10 -> inclusive end Feb 9.
    """
    next_anchor = payment_date + relativedelta_for_billing(months, billing_cycle)
    return next_anchor - timedelta(days=1)


def next_payment_due_date(payment_date: date, months: int, billing_cycle: str) -> date:
    """First day of the next billing cycle (day after inclusive period end)."""
    return payment_date + relativedelta_for_billing(months, billing_cycle)


def subscription_plan_value_from_product(product: str) -> str:
    """Map BillingHistory.product label to Subscription.plan stored value (.value)."""
    p = (product or "").lower()
    if "standard" in p or p == "standard plan":
        return SubscriptionPlan.STANDARD.value
    if "multi-branch" in p or "multi_branch" in p:
        return SubscriptionPlan.MULTI_BRANCH.value
    if "premium" in p or "efris" in p:
        return SubscriptionPlan.PREMIUM.value
    if "starter" in p and "pack" not in p:
        return SubscriptionPlan.STARTER.value
    if "business" in p:
        return SubscriptionPlan.BUSINESS.value
    if "pro" in p:
        return SubscriptionPlan.PRO.value
    return SubscriptionPlan.STANDARD.value


def coverage_period_label(
    billing_date: date | None, metadata: Mapping[str, Any] | None
) -> str:
    """Human-readable inclusive coverage range for receipts / reminders."""
    if billing_date is None:
        return "—"
    months, billing_cycle = parse_billing_period_from_metadata(metadata)
    end = subscription_period_end_inclusive(billing_date, months, billing_cycle)
    start_s = billing_date.strftime("%d %B %Y")
    end_s = end.strftime("%d %B %Y")
    return f"{start_s} – {end_s}"


def aware_start_of_day(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, datetime.min.time()))
