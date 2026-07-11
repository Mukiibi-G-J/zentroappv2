"""
Registry of models that participate in branch (Global Dimension 1) / dimension set backfill.

Single source of truth for audit, backfill, and verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from django.apps import apps as django_apps


@dataclass(frozen=True)
class DimensionModelEntry:
    """One auditable / backfillable model."""

    app_label: str
    model_name: str
    has_dimension_set: bool
    include_in_backfill: bool = True


# (app_label, model_name) — has_dimension_set: True = backfill g1 + dimension_set; False = g1 only
MODELS_G1_AND_SET: List[tuple[str, str]] = [
    ("financials", "GeneralLedgerEntry"),
    ("sales", "SalesInvoice"),
    ("sales", "PostedSalesInvoice"),
    ("sales", "SalesCreditMemo"),
    ("sales", "SalesInvoiceLine"),
    ("sales", "PostedSalesInvoiceLine"),
    ("sales", "SalesCreditMemoLine"),
    ("sales", "SalesOrderLine"),
    ("sales", "CustomerLedgerEntry"),
    ("sales", "DetailedCustomerLedgerEntry"),
    ("purchases", "PurchaseInvoice"),
    ("purchases", "PostedPurchaseInvoice"),
    ("purchases", "PurchaseCreditMemo"),
    ("purchases", "PurchaseInvoiceLine"),
    ("purchases", "PostedPurchaseInvoiceLine"),
    ("purchases", "PurchaseCreditMemoLine"),
    ("purchases", "VendorLedger"),
    ("purchases", "DetailedVendorLedgerEntry"),
    ("items", "ItemLedgerEntries"),
    ("items", "ValueEntry"),
    ("items", "ItemJournal"),
    ("prepayment", "Preayment"),
    ("prepayment", "PreaymentLine"),
    ("expenses", "Expense"),
    ("bank_account", "BankAccountLedgerEntry"),
    ("production", "ProductionOrderLine"),
]

MODELS_G1_ONLY: List[tuple[str, str]] = [
    ("loans", "Loan"),
    ("loans", "LoanRepayment"),
    ("restaurant_management", "RestaurantOrder"),
    ("financials", "VatEntry"),
]

AUDIT_OPTIONAL: List[tuple[str, str]] = [
    ("authentication", "CustomUser"),
]


def all_registry_entries() -> List[DimensionModelEntry]:
    out: List[DimensionModelEntry] = []
    for app_label, model_name in MODELS_G1_AND_SET:
        out.append(
            DimensionModelEntry(
                app_label=app_label,
                model_name=model_name,
                has_dimension_set=True,
            )
        )
    for app_label, model_name in MODELS_G1_ONLY:
        out.append(
            DimensionModelEntry(
                app_label=app_label,
                model_name=model_name,
                has_dimension_set=False,
            )
        )
    for app_label, model_name in AUDIT_OPTIONAL:
        out.append(
            DimensionModelEntry(
                app_label=app_label,
                model_name=model_name,
                has_dimension_set=False,
                include_in_backfill=False,
            )
        )
    return out


def get_model_for_entry(entry: DimensionModelEntry):
    return django_apps.get_model(entry.app_label, entry.model_name)


def backfill_entries() -> List[DimensionModelEntry]:
    return [e for e in all_registry_entries() if e.include_in_backfill]


def model_has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def audit_entries(include_optional: bool = True) -> List[DimensionModelEntry]:
    all_e = all_registry_entries()
    if include_optional:
        return all_e
    return [e for e in all_e if e.include_in_backfill]
