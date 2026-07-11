from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from company.enums import SubscriptionStatus
from company.subscription_grace import (
    access_lock_date_for,
    expiry_kind_for_subscription,
    grace_days_for_company,
    in_grace_period,
    payment_due_date,
    period_end_date,
    reminder_offsets_for_company,
)


class SubscriptionGraceMathTests(SimpleTestCase):
    def test_paid_period_lock_matches_example(self):
        sub = SimpleNamespace(
            status=SubscriptionStatus.ACTIVE.value,
            trial_period_end_date=date(2026, 4, 1),
            subscription_end_date=date(2026, 5, 29),
            company=SimpleNamespace(subscription_grace_days=3),
        )
        self.assertEqual(period_end_date(sub), date(2026, 5, 29))
        self.assertEqual(payment_due_date(sub), date(2026, 5, 30))
        self.assertEqual(access_lock_date_for(sub), date(2026, 6, 2))
        self.assertTrue(in_grace_period(date(2026, 6, 1), sub, sub.company))
        self.assertFalse(in_grace_period(date(2026, 6, 2), sub, sub.company))

    def test_trial_uses_trial_end(self):
        sub = SimpleNamespace(
            status=SubscriptionStatus.TRIAL.value,
            trial_period_end_date=date(2026, 5, 10),
            subscription_end_date=date(2026, 5, 10),
            company=SimpleNamespace(subscription_grace_days=2),
        )
        self.assertEqual(period_end_date(sub), date(2026, 5, 10))
        self.assertEqual(payment_due_date(sub), date(2026, 5, 11))
        self.assertEqual(access_lock_date_for(sub), date(2026, 5, 13))

    def test_grace_days_default(self):
        self.assertEqual(grace_days_for_company(None), 2)
        self.assertEqual(grace_days_for_company(SimpleNamespace()), 2)

    def test_grace_days_zero_means_lock_on_due_date(self):
        c = SimpleNamespace(subscription_grace_days=0)
        self.assertEqual(grace_days_for_company(c), 0)
        sub = SimpleNamespace(
            status=SubscriptionStatus.ACTIVE.value,
            trial_period_end_date=date(2026, 4, 1),
            subscription_end_date=date(2026, 5, 1),
            company=c,
        )
        self.assertEqual(payment_due_date(sub), date(2026, 5, 2))
        self.assertEqual(access_lock_date_for(sub, c), date(2026, 5, 2))
        self.assertFalse(in_grace_period(date(2026, 5, 2), sub, c))
        self.assertFalse(in_grace_period(date(2026, 5, 1), sub, c))

    def test_reminder_offsets_default_none(self):
        c = SimpleNamespace(subscription_grace_days=3, grace_reminder_offsets=None)
        self.assertEqual(reminder_offsets_for_company(c), [0, 1, 2])

    def test_reminder_offsets_custom(self):
        c = SimpleNamespace(subscription_grace_days=5, grace_reminder_offsets=[0, 2, 4])
        self.assertEqual(reminder_offsets_for_company(c), [0, 2, 4])

    def test_expiry_kind_trial_unpaid(self):
        sub = SimpleNamespace(
            status=SubscriptionStatus.TRIAL.value,
            is_paid=False,
        )
        self.assertEqual(expiry_kind_for_subscription(sub), "trial")

    def test_expiry_kind_paid_plan(self):
        sub = SimpleNamespace(
            status=SubscriptionStatus.ACTIVE.value,
            is_paid=True,
        )
        self.assertEqual(expiry_kind_for_subscription(sub), "subscription")

    def test_expiry_kind_trial_but_paid_flag(self):
        sub = SimpleNamespace(
            status=SubscriptionStatus.TRIAL.value,
            is_paid=True,
        )
        self.assertEqual(expiry_kind_for_subscription(sub), "subscription")
