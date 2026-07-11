from datetime import date

from django.test import SimpleTestCase

from financials.services.period_formula import ReportPeriod, resolve_comparison_period


class ResolveComparisonPeriodTests(SimpleTestCase):
    def test_single_day_filter_uses_exact_day_for_current_month_column(self):
        base = ReportPeriod(date(2026, 7, 11), date(2026, 7, 11), "Jul 11, 2026")
        period = resolve_comparison_period(base, "0M")
        self.assertEqual(period.start_date, date(2026, 7, 11))
        self.assertEqual(period.end_date, date(2026, 7, 11))

    def test_single_day_filter_shifts_previous_month_column(self):
        base = ReportPeriod(date(2026, 7, 11), date(2026, 7, 11), "Jul 11, 2026")
        period = resolve_comparison_period(base, "-1M")
        self.assertEqual(period.start_date, date(2026, 6, 11))
        self.assertEqual(period.end_date, date(2026, 6, 11))

    def test_partial_month_filter_preserves_range(self):
        base = ReportPeriod(date(2026, 7, 1), date(2026, 7, 15), "Jul 1 – Jul 15, 2026")
        period = resolve_comparison_period(base, "0M")
        self.assertEqual(period.start_date, date(2026, 7, 1))
        self.assertEqual(period.end_date, date(2026, 7, 15))

    def test_full_calendar_month_still_uses_calendar_month(self):
        base = ReportPeriod(date(2026, 7, 1), date(2026, 7, 31), "July 2026")
        period = resolve_comparison_period(base, "-1M")
        self.assertEqual(period.start_date, date(2026, 6, 1))
        self.assertEqual(period.end_date, date(2026, 6, 30))

    def test_year_to_date_ends_on_filter_end_date(self):
        base = ReportPeriod(date(2026, 7, 11), date(2026, 7, 11), "Jul 11, 2026")
        period = resolve_comparison_period(base, "0Y")
        self.assertEqual(period.start_date, date(2026, 1, 1))
        self.assertEqual(period.end_date, date(2026, 7, 11))
