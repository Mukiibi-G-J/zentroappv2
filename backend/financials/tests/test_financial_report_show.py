from types import SimpleNamespace

from django.test import SimpleTestCase

from financials import enums
from financials.services.financial_report_service import (
    _apply_section_visibility,
    _should_show_row,
)


def _line(**kwargs):
    defaults = {
        "line_no": 1,
        "row_no": "1",
        "row_type": enums.FinancialReportRowType.Posting.value,
        "show": enums.FinancialReportShowLine.If_Amount_Not_Zero.value,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class FinancialReportShowTests(SimpleTestCase):
    def test_if_amount_not_zero_hides_zero_posting_row(self):
        line = _line(show=enums.FinancialReportShowLine.If_Amount_Not_Zero.value)
        self.assertFalse(_should_show_row(line, {"col_1": 0.0, "col_2": 0.0}, False))

    def test_if_any_column_not_zero_alias(self):
        line = _line(show=enums.FinancialReportShowLine.If_Any_Column_Not_Zero.value)
        self.assertTrue(_should_show_row(line, {"col_1": 0.0, "col_2": 10.0}, False))

    def test_when_positive_balance(self):
        line = _line(show=enums.FinancialReportShowLine.When_Positive_Balance.value)
        self.assertTrue(_should_show_row(line, {"col_1": 5.0}, False))
        self.assertFalse(_should_show_row(line, {"col_1": -5.0}, False))

    def test_section_collapses_when_all_postings_zero(self):
        begin = _line(
            line_no=11000,
            row_type=enums.FinancialReportRowType.Begin_Total.value,
            show=enums.FinancialReportShowLine.If_Amount_Not_Zero.value,
        )
        posting = _line(
            line_no=11100,
            row_type=enums.FinancialReportRowType.Posting.value,
            show=enums.FinancialReportShowLine.If_Amount_Not_Zero.value,
        )
        end = _line(
            line_no=11999,
            row_type=enums.FinancialReportRowType.End_Total.value,
            show=enums.FinancialReportShowLine.If_Amount_Not_Zero.value,
        )
        row_lines = [begin, posting, end]
        amounts = {
            11000: {"col_1": 0.0},
            11100: {"col_1": 0.0},
            11999: {"col_1": 0.0},
        }
        visibility = {
            11000: True,
            11100: _should_show_row(posting, amounts[11100], False),
            11999: _should_show_row(end, amounts[11999], False),
        }
        _apply_section_visibility(row_lines, visibility, amounts)
        self.assertFalse(visibility[11000])
        self.assertFalse(visibility[11100])
        self.assertFalse(visibility[11999])

    def test_section_keeps_begin_total_when_posting_has_amount(self):
        begin = _line(
            line_no=11000,
            row_type=enums.FinancialReportRowType.Begin_Total.value,
        )
        posting = _line(
            line_no=11100,
            row_type=enums.FinancialReportRowType.Posting.value,
        )
        end = _line(
            line_no=11999,
            row_type=enums.FinancialReportRowType.End_Total.value,
        )
        row_lines = [begin, posting, end]
        amounts = {
            11000: {"col_1": 0.0},
            11100: {"col_1": 2000.0},
            11999: {"col_1": 2000.0},
        }
        visibility = {
            11000: False,
            11100: _should_show_row(posting, amounts[11100], False),
            11999: _should_show_row(end, amounts[11999], False),
        }
        _apply_section_visibility(row_lines, visibility, amounts)
        self.assertTrue(visibility[11000])
        self.assertTrue(visibility[11100])
        self.assertTrue(visibility[11999])
