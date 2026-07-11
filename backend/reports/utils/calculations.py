"""
Shared calculation utilities for reports.
Common formulas and mathematical operations.
"""

from decimal import Decimal
from typing import Union


def calculate_growth_percentage(
    current_value: Union[int, float, Decimal],
    previous_value: Union[int, float, Decimal],
) -> float:
    """
    Calculate percentage growth/decline between two values.

    Args:
        current_value: Current period value
        previous_value: Previous period value

    Returns:
        Percentage change (positive for growth, negative for decline)
        Returns 0 if previous_value is 0
    """
    if previous_value == 0:
        return 0.0 if current_value == 0 else 100.0

    change = float(current_value) - float(previous_value)
    return (change / float(previous_value)) * 100


def calculate_profit_margin(
    profit: Union[int, float, Decimal], revenue: Union[int, float, Decimal]
) -> float:
    """
    Calculate profit margin percentage.

    Args:
        profit: Net profit amount
        revenue: Total revenue amount

    Returns:
        Profit margin as percentage
        Returns 0 if revenue is 0
    """
    if revenue == 0:
        return 0.0

    return (float(profit) / float(revenue)) * 100


def calculate_average(total: Union[int, float, Decimal], count: int) -> float:
    """
    Calculate average value.

    Args:
        total: Sum of values
        count: Number of items

    Returns:
        Average value
        Returns 0 if count is 0
    """
    if count == 0:
        return 0.0

    return float(total) / count


def safe_divide(
    numerator: Union[int, float, Decimal],
    denominator: Union[int, float, Decimal],
    default: float = 0.0,
) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: Top number
        denominator: Bottom number
        default: Value to return if division by zero

    Returns:
        Result of division or default
    """
    if denominator == 0:
        return default

    return float(numerator) / float(denominator)
