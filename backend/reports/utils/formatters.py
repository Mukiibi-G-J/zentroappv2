"""
Data formatting utilities for reports.
Currency formatting, date formatting, etc.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Union
from decimal import Decimal

from financials.currency import get_local_currency_code


def format_currency(
    amount: Union[int, float, Decimal],
    currency: Optional[str] = None,
) -> str:
    """
    Format amount as currency string.

    Args:
        amount: Numeric amount
        currency: Currency code (defaults to tenant local currency)

    Returns:
        Formatted currency string (e.g., "UGX 1,234,567")
    """
    code = (currency or get_local_currency_code()).upper()
    try:
        return f"{code} {float(amount):,.0f}"
    except (ValueError, TypeError):
        return f"{code} 0"


def format_percentage(value: Union[int, float], decimal_places: int = 1) -> str:
    """
    Format value as percentage string.
    
    Args:
        value: Numeric value
        decimal_places: Number of decimal places
    
    Returns:
        Formatted percentage string (e.g., "12.5%")
    """
    try:
        return f"{float(value):.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"


def get_date_range(period_type: str, reference_date: date = None):
    """
    Get start and end dates for a period type.
    
    Args:
        period_type: One of 'today', 'yesterday', 'this_week', 'last_week', 
                     'this_month', 'last_month', 'this_year'
        reference_date: Reference date (default: today)
    
    Returns:
        Tuple of (start_date, end_date)
    """
    if reference_date is None:
        reference_date = date.today()
    
    if period_type == "today":
        return reference_date, reference_date
    
    elif period_type == "yesterday":
        yesterday = reference_date - timedelta(days=1)
        return yesterday, yesterday
    
    elif period_type == "this_week":
        # Week starts on Monday (weekday 0)
        start = reference_date - timedelta(days=reference_date.weekday())
        end = start + timedelta(days=6)
        return start, end
    
    elif period_type == "last_week":
        this_week_start = reference_date - timedelta(days=reference_date.weekday())
        start = this_week_start - timedelta(days=7)
        end = start + timedelta(days=6)
        return start, end
    
    elif period_type == "this_month":
        start = reference_date.replace(day=1)
        # Last day of month
        if reference_date.month == 12:
            end = reference_date.replace(month=12, day=31)
        else:
            next_month = reference_date.replace(month=reference_date.month + 1, day=1)
            end = next_month - timedelta(days=1)
        return start, end
    
    elif period_type == "last_month":
        first_this_month = reference_date.replace(day=1)
        end = first_this_month - timedelta(days=1)  # Last day of previous month
        start = end.replace(day=1)  # First day of previous month
        return start, end
    
    elif period_type == "this_year":
        start = reference_date.replace(month=1, day=1)
        end = reference_date.replace(month=12, day=31)
        return start, end
    
    else:
        raise ValueError(f"Invalid period_type: {period_type}")


def validate_date_range(start_date: date, end_date: date) -> bool:
    """
    Validate that date range is logical.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        True if valid, raises ValueError if invalid
    """
    if end_date < start_date:
        raise ValueError("End date must be greater than or equal to start date")
    
    return True

