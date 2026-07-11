"""Tenant local currency (LCY) helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DEFAULT_LOCAL_CURRENCY_CODE = "UGX"

_DATA_PATH = Path(__file__).resolve().parent / "data" / "iso4217_currencies.json"


@lru_cache(maxsize=1)
def get_currency_catalog() -> tuple[dict[str, dict], ...]:
    """Load ISO 4217 catalog as tuple of dicts keyed by code for immutability."""
    with _DATA_PATH.open(encoding="utf-8") as f:
        rows = json.load(f)
    by_code = {
        str(row["code"]).upper(): {
            "code": str(row["code"]).upper(),
            "name": str(row["name"]),
            "minor_units": int(row.get("minor_units", 2)),
        }
        for row in rows
    }
    return (by_code,)


def _catalog_by_code() -> dict[str, dict]:
    return get_currency_catalog()[0]


def get_allowed_local_currency_codes() -> frozenset[str]:
    return frozenset(_catalog_by_code().keys())


def get_currency_minor_units(code: str | None) -> int:
    """Return ISO minor-unit exponent (0 = no decimal places)."""
    if not code:
        return 2
    entry = _catalog_by_code().get(str(code).strip().upper())
    if entry:
        return int(entry["minor_units"])
    return 2


def get_local_currency_code() -> str:
    """Return the tenant's local currency code from General Ledger Setup."""
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        if gl_setup and gl_setup.local_currency_code:
            return str(gl_setup.local_currency_code).upper()
    except Exception:
        pass
    return DEFAULT_LOCAL_CURRENCY_CODE


def normalize_local_currency_code(value: str | None) -> str | None:
    """Validate and normalize a local currency code; returns None if invalid."""
    if not value:
        return None
    code = str(value).strip().upper()
    if len(code) != 3 or not code.isalpha():
        return None
    if code not in _catalog_by_code():
        return None
    return code


def list_currencies_for_api() -> list[dict]:
    """Sorted currency list for API responses."""
    catalog = _catalog_by_code()
    return [catalog[code] for code in sorted(catalog.keys())]
