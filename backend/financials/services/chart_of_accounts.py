"""Chart of accounts helpers (Business Central–style indentation)."""

from __future__ import annotations

from dataclasses import dataclass

from financials.models import G_LAccount

MAX_INDENT_LEVEL = 10


@dataclass
class IndentChartResult:
    updated: int
    errors: list[str]


def indent_chart_of_accounts(
    queryset=None,
    *,
    max_depth: int = MAX_INDENT_LEVEL,
) -> IndentChartResult:
    """
    Recompute indentation for all G/L accounts in account-number order.

    Accounts between a Begin-Total and matching End-Total are indented one level.
    """
    if queryset is None:
        queryset = G_LAccount.objects.all()

    accounts = list(queryset.order_by('no'))
    stack: list[G_LAccount] = []
    level = 0
    updated = 0
    errors: list[str] = []

    for account in accounts:
        if account.accounttype == 'End-Total':
            if not stack:
                errors.append(f'End-Total {account.no} is missing a Begin-Total.')
                continue
            begin_total = stack.pop()
            if not account.totaling:
                account.totaling = f'{begin_total.no}..{account.no}'
            level = max(level - 1, 0)

        account.indentation = level
        account.save()
        updated += 1

        if account.accounttype == 'Begin-Total':
            level += 1
            if level > max_depth:
                errors.append(
                    f'Begin-Total {account.no} exceeds maximum indent depth ({max_depth}).',
                )
                level = max_depth
            stack.append(account)

    return IndentChartResult(updated=updated, errors=errors)
