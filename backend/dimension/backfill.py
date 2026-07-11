"""
Backfill null global dimensions and dimension_set per tenant schema (idempotent).
Used by the data migration and management command.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from django.apps import apps
from django.core.exceptions import FieldError
from django.db import connection, transaction
from django.db.models import Q
from django.db.utils import DatabaseError, ProgrammingError

from dimension.branch_dimension_registry import (
    DimensionModelEntry,
    backfill_entries,
    get_model_for_entry,
    model_has_field,
)
from dimension.models import DimensionBackfillAudit

logger = logging.getLogger(__name__)


@dataclass
class TableBackfillResult:
    app_label: str
    model_name: str
    label: str
    matched_rows: int
    updated: int
    skipped: str = ""


def run_branch_dimension_backfill(
    *,
    allow_multiple_branch_values: bool = False,
    write_audit: bool = True,
) -> Tuple[List[TableBackfillResult], Optional[str]]:
    """
    Backfill all registered models in the current DB schema.

    Returns (results, error). If error is not None, no updates were applied.
    """
    from dimension.utils import resolve_default_branch_for_tenant

    branch, dim_set, err = resolve_default_branch_for_tenant(
        allow_multiple_branch_values=allow_multiple_branch_values
    )
    if err:
        return [], err
    if branch is None or branch.pk is None:
        return [], "Branch DimensionValue is missing."

    if dim_set is None:
        for entry in backfill_entries():
            if not entry.has_dimension_set:
                continue
            try:
                model = get_model_for_entry(entry)
            except LookupError:
                continue
            if not model._meta.managed or model._meta.proxy:
                continue
            if model_has_field(model, "dimension_set"):
                return [], (
                    "Could not build DimensionSet for backfill; "
                    "check GeneralLedgerSetup, Dimension BRANCH, and dimension values."
                )

    g2_id: Optional[int] = None
    if dim_set and dim_set.pk:
        from financials.models import GeneralLedgerSetup
        from dimension.models import get_dimension_value_from_set

        gls = GeneralLedgerSetup.objects.first()
        if gls and gls.global_dimension_2_id:
            g2o = get_dimension_value_from_set(dim_set, gls.global_dimension_2)
            g2_id = g2o.pk if g2o else None

    if write_audit:
        audit_table = DimensionBackfillAudit._meta.db_table
        if audit_table not in connection.introspection.table_names():
            return [], (
                f'Table "{audit_table}" is missing in this schema. '
                "Apply `dimension.0007_dimension_backfill_audit_and_data` (e.g. "
                "`migrate_schemas` for the tenant) or run with write_audit off "
                "(`--no-audit` on `backfill_branch_dimensions`)."
            )

    # One atomic block per model: PostgreSQL aborts the current transaction on the first
    # failed SQL; catching ProgrammingError in one model must not leave the connection
    # poisoned for the next. Nested atomic = savepoint; set_rollback on soft-skip.
    results: List[TableBackfillResult] = []
    for entry in backfill_entries():
        with transaction.atomic():
            r = _backfill_model(
                entry,
                branch=branch,
                dim_set=dim_set,
                g2_id=g2_id,
                write_audit=write_audit,
            )
            results.append(r)
    return results, None


def _backfill_model(
    entry: DimensionModelEntry,
    *,
    branch: Any,
    dim_set: Any,
    g2_id: Optional[int],
    write_audit: bool,
) -> TableBackfillResult:
    label = f"{entry.app_label}.{entry.model_name}"
    try:
        model = get_model_for_entry(entry)
    except LookupError as e:
        return TableBackfillResult(
            entry.app_label, entry.model_name, label, 0, 0, skipped=str(e)
        )

    if model._meta.proxy or not model._meta.managed:
        return TableBackfillResult(
            entry.app_label, entry.model_name, label, 0, 0, skipped="proxy/unmanaged"
        )
    if not model_has_field(model, "global_dimension_1"):
        return TableBackfillResult(
            entry.app_label, entry.model_name, label, 0, 0, skipped="no global_dimension_1"
        )

    has_ds_field = model_has_field(model, "dimension_set")
    has_ds = has_ds_field and entry.has_dimension_set
    has_g2 = model_has_field(model, "global_dimension_2")
    # Ledger-style models (e.g. CustomerLedgerEntry) use non-"id" primary keys.
    pk_att = model._meta.pk.get_attname()

    if has_ds and dim_set is not None:
        q1 = model.objects.filter(global_dimension_1__isnull=True)
        q2 = model.objects.filter(
            global_dimension_1__isnull=False, dimension_set__isnull=True
        )
    else:
        q1 = model.objects.filter(global_dimension_1__isnull=True)
        q2 = model.objects.none()

    try:
        matched = q1.count() + q2.count()
        if matched == 0:
            return TableBackfillResult(
                entry.app_label, entry.model_name, label, 0, 0
            )

        if write_audit:
            vf: List[str] = [pk_att, "global_dimension_1_id"]
            if has_g2:
                vf.append("global_dimension_2_id")
            if has_ds:
                vf.append("dimension_set_id")
            seen = set()
            rows = []
            for qs in (q1, q2):
                for row in qs.values(*vf).iterator():
                    if row[pk_att] in seen:
                        continue
                    seen.add(row[pk_att])
                    rows.append(row)
            audit_batch = [
                DimensionBackfillAudit(
                    app_label=entry.app_label,
                    model_name=entry.model_name,
                    object_id=row[pk_att],
                    prev_global_dimension_1_id=row.get("global_dimension_1_id"),
                    prev_global_dimension_2_id=row.get("global_dimension_2_id")
                    if has_g2
                    else None,
                    prev_dimension_set_id=row.get("dimension_set_id")
                    if has_ds
                    else None,
                )
                for row in rows
            ]
            DimensionBackfillAudit.objects.bulk_create(audit_batch, batch_size=2000)

        n = 0
        u_all = {
            "global_dimension_1_id": branch.pk,
        }
        if has_ds and dim_set is not None:
            u_all["dimension_set_id"] = dim_set.pk
        if has_g2 and g2_id is not None:
            u_all["global_dimension_2_id"] = g2_id
        n += q1.update(**u_all)

        if has_ds and dim_set is not None:
            q2_ids = list(q2.values_list("pk", flat=True))
            if q2_ids:
                n += model.objects.filter(pk__in=q2_ids).update(
                    dimension_set_id=dim_set.pk
                )
                if has_g2 and g2_id is not None:
                    n += model.objects.filter(
                        pk__in=q2_ids, global_dimension_2__isnull=True
                    ).update(global_dimension_2_id=g2_id)

        return TableBackfillResult(
            entry.app_label, entry.model_name, label, matched, n
        )
    except (ProgrammingError, DatabaseError) as e:
        transaction.set_rollback(True)
        return TableBackfillResult(
            entry.app_label,
            entry.model_name,
            label,
            0,
            0,
            skipped=f"schema drift (apply app migrations, then re-run backfill): {e!s}"[:500],
        )
    except FieldError as e:
        transaction.set_rollback(True)
        return TableBackfillResult(
            entry.app_label,
            entry.model_name,
            label,
            0,
            0,
            skipped=f"orm: {e!s}"[:500],
        )


def reverse_branch_dimension_backfill() -> int:
    """Restore from DimensionBackfillAudit in the current schema. Returns number of ORM update calls."""
    n = 0
    for audit in DimensionBackfillAudit.objects.all().order_by("id").iterator(
        chunk_size=500
    ):
        try:
            model = apps.get_model(audit.app_label, audit.model_name)
        except LookupError:
            continue
        if not model_has_field(model, "global_dimension_1"):
            continue
        has_ds = model_has_field(model, "dimension_set")
        has_g2 = model_has_field(model, "global_dimension_2")
        u: dict = {
            "global_dimension_1_id": audit.prev_global_dimension_1_id,
        }
        if has_g2:
            u["global_dimension_2_id"] = audit.prev_global_dimension_2_id
        if has_ds:
            u["dimension_set_id"] = audit.prev_dimension_set_id
        n += model.objects.filter(pk=audit.object_id).update(**u)
    DimensionBackfillAudit.objects.all().delete()
    return n
