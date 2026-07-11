"""BC-style comparison period formulas for financial report columns (e.g. 0M, -1M, 0Y)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

_PERIOD_RE = re.compile(r"^(-?\d+)([MYQDW])$", re.IGNORECASE)


@dataclass
class ReportPeriod:
    start_date: date
    end_date: date
    label: str


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _shift_month(anchor: date, offset: int) -> tuple[date, date]:
    year = anchor.year
    month = anchor.month + offset
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return _month_bounds(year, month)


def _add_months(value: date, months: int) -> date:
    year = value.year
    month = value.month + months
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    last_day = _month_bounds(year, month)[1].day
    return date(year, month, min(value.day, last_day))


def _shift_range_by_months(start: date, end: date, months: int) -> tuple[date, date]:
    return _add_months(start, months), _add_months(end, months)


def _is_full_calendar_month(start: date, end: date) -> bool:
    if start.year != end.year or start.month != end.month:
        return False
    month_start, month_end = _month_bounds(start.year, start.month)
    return start == month_start and end == month_end


def _range_label(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%b %d, %Y")
    return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"


def resolve_comparison_period(
    base: ReportPeriod,
    formula: str | None,
    period_type: str | None = None,
) -> ReportPeriod:
    """
    Shift the report base period using a BC comparison period formula.

    When the base period is a custom/filtered range (not a full calendar month),
    month formulas preserve that range instead of expanding to whole months.

    Examples:
      0M  = same period as the report filter (or calendar month when filter is a full month)
      -1M = previous month, or the same day/range shifted back one month
      0Y  = year-to-date through the report period end date
      -1Y = previous calendar year
    """
    del period_type  # reserved for future period-type-specific rules

    raw = (formula or "0M").strip().upper().replace(" ", "")
    if not raw:
        raw = "0M"

    match = _PERIOD_RE.match(raw)
    if not match:
        return base

    offset = int(match.group(1))
    unit = match.group(2).upper()
    anchor = base.end_date
    use_filtered_range = not _is_full_calendar_month(base.start_date, base.end_date)

    if unit == "M":
        if use_filtered_range:
            if offset == 0:
                return base
            start, end = _shift_range_by_months(base.start_date, base.end_date, offset)
            if start.month == end.month and start.year == end.year:
                label = start.strftime("%B %Y")
            else:
                label = _range_label(start, end)
            return ReportPeriod(start, end, label)

        start, end = _shift_month(anchor, offset)
        return ReportPeriod(start, end, start.strftime("%B %Y"))

    if unit == "Y":
        year = anchor.year + offset
        start = date(year, 1, 1)
        if offset == 0:
            end = anchor if use_filtered_range else base.end_date
            label = f"Jan – {end.strftime('%b %Y')}"
        else:
            end = date(year, 12, 31)
            label = str(year)
        return ReportPeriod(start, end, label)

    if unit == "Q":
        quarter = (anchor.month - 1) // 3 + offset
        year = anchor.year
        while quarter < 0:
            quarter += 4
            year -= 1
        while quarter > 3:
            quarter -= 4
            year += 1
        start_month = quarter * 3 + 1
        start, end = _month_bounds(year, start_month + 2)
        start = date(year, start_month, 1)
        if use_filtered_range and offset == 0:
            return ReportPeriod(base.start_date, min(base.end_date, end), f"Q{quarter + 1} {year}")
        return ReportPeriod(start, end, f"Q{quarter + 1} {year}")

    if unit == "D":
        if use_filtered_range and offset == 0:
            return base
        span_days = (base.end_date - base.start_date).days
        target_end = anchor + timedelta(days=offset)
        target_start = target_end - timedelta(days=span_days)
        return ReportPeriod(target_start, target_end, _range_label(target_start, target_end))

    if unit == "W":
        if use_filtered_range and offset == 0:
            return base
        week_start = anchor - timedelta(days=anchor.weekday()) + timedelta(weeks=offset)
        week_end = week_start + timedelta(days=6)
        return ReportPeriod(
            week_start,
            week_end,
            f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}",
        )

    return base
