from datetime import date

from django.test import SimpleTestCase

from company.subscription_billing import (
    coverage_period_label,
    next_payment_due_date,
    parse_billing_period_from_metadata,
    relativedelta_for_billing,
    subscription_period_end_inclusive,
    subscription_plan_value_from_product,
)


class SubscriptionBillingHelpersTests(SimpleTestCase):
    def test_monthly_one_month_jan10(self):
        start = date(2026, 1, 10)
        end = subscription_period_end_inclusive(start, 1, "monthly")
        self.assertEqual(end, date(2026, 2, 9))
        self.assertEqual(next_payment_due_date(start, 1, "monthly"), date(2026, 2, 10))

    def test_monthly_jan31_clamps_february(self):
        start = date(2025, 1, 31)
        end = subscription_period_end_inclusive(start, 1, "monthly")
        self.assertEqual(next_payment_due_date(start, 1, "monthly"), date(2025, 2, 28))
        self.assertEqual(end, date(2025, 2, 27))

    def test_monthly_jan31_leap_year(self):
        start = date(2024, 1, 31)
        self.assertEqual(next_payment_due_date(start, 1, "monthly"), date(2024, 2, 29))
        self.assertEqual(subscription_period_end_inclusive(start, 1, "monthly"), date(2024, 2, 28))

    def test_monthly_three_months(self):
        start = date(2026, 1, 10)
        end = subscription_period_end_inclusive(start, 3, "monthly")
        self.assertEqual(next_payment_due_date(start, 3, "monthly"), date(2026, 4, 10))
        self.assertEqual(end, date(2026, 4, 9))

    def test_yearly_one_year(self):
        start = date(2026, 1, 10)
        end = subscription_period_end_inclusive(start, 1, "yearly")
        self.assertEqual(next_payment_due_date(start, 1, "yearly"), date(2027, 1, 10))
        self.assertEqual(end, date(2027, 1, 9))

    def test_yearly_two_years(self):
        start = date(2026, 3, 15)
        end = subscription_period_end_inclusive(start, 2, "yearly")
        self.assertEqual(end, date(2028, 3, 14))

    def test_parse_metadata_defaults(self):
        self.assertEqual(parse_billing_period_from_metadata({}), (1, "monthly"))
        self.assertEqual(parse_billing_period_from_metadata({"months": "3"}), (3, "monthly"))
        self.assertEqual(
            parse_billing_period_from_metadata({"months": 2, "billing_cycle": "yearly"}),
            (2, "yearly"),
        )
        self.assertEqual(
            parse_billing_period_from_metadata({"billing_cycle": "invalid"}),
            (1, "monthly"),
        )

    def test_coverage_period_label(self):
        lbl = coverage_period_label(
            date(2026, 1, 10), {"months": 1, "billing_cycle": "monthly"}
        )
        self.assertIn("10 January 2026", lbl)
        self.assertIn("09 February 2026", lbl)

    def test_plan_from_product_standard(self):
        from company.enums import SubscriptionPlan

        v = subscription_plan_value_from_product("Standard Plan")
        self.assertEqual(v, SubscriptionPlan.STANDARD.value)
        self.assertEqual(
            subscription_plan_value_from_product("Acme Standard"),
            SubscriptionPlan.STANDARD.value,
        )
