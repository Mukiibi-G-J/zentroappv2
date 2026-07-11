"""
Dimension utilities for default branch resolution and backfill.
"""
from typing import Any, Optional, Tuple

from django.db.utils import DatabaseError, ProgrammingError

from .models import Dimension, DimensionValue


def resolve_default_branch_for_tenant(
    *,
    allow_multiple_branch_values: bool = False,
) -> Tuple[Optional[DimensionValue], Optional[Any], Optional[str]]:
    """
    Resolve the tenant's default branch DimensionValue and matching DimensionSet for backfill.

    Returns (branch_value, dimension_set, error_message). If error_message is not None, abort backfill.
    - When `allow_multiple_branch_values` is False and more than one DimensionValue exists
      for the G/L global dimension 1, returns an error (safe default for production).
    - Fills a second global dimension (G2) in the set only if GeneralLedgerSetup has
      global_dimension_2 and exactly one DimensionValue exists for that dimension.
    """
    from dimension.models import get_posting_dimension_payload
    from financials.models import GeneralLedgerSetup

    try:
        gl = GeneralLedgerSetup.objects.first()
        dim = None
        if gl and gl.global_dimension_1_id:
            dim = gl.global_dimension_1
        if not dim:
            dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        if not dim:
            return (
                None,
                None,
                "No branch dimension: set GeneralLedgerSetup.global_dimension_1 or Dimension BRANCH.",
            )
    except (ProgrammingError, DatabaseError) as e:
        return (
            None,
            None,
            f"SCHEMA_DRIFT: could not resolve branch dimension (dimension/financials tables out of date): {e!s}"[:300],
        )

    q = DimensionValue.objects.filter(dimension_code=dim).order_by("code")
    count = q.count()
    if count == 0:
        return None, None, f"No DimensionValue for dimension {dim.code!r}."
    if count > 1 and not allow_multiple_branch_values:
        return (
            None,
            None,
            f"Multiple branch DimensionValue rows for {dim.code!r} ({count}). "
            "Re-run with allow_multiple_branch_values=True to use the first by code, "
            "or reduce to one value per tenant.",
        )
    branch = q.first()
    g2_val = None
    if gl and gl.global_dimension_2_id:
        g2q = DimensionValue.objects.filter(
            dimension_code=gl.global_dimension_2
        ).order_by("code")
        g2c = g2q.count()
        if g2c == 1:
            g2_val = g2q.first()
        elif g2c > 1 and allow_multiple_branch_values:
            g2_val = g2q.first()

    payload = get_posting_dimension_payload(
        global_dimension_1=branch,
        global_dimension_2=g2_val,
        gl_setup=gl,
    )
    dim_set = payload.get("dimension_set")
    g1o = payload.get("global_dimension_1")
    g2o = payload.get("global_dimension_2")
    out_branch = g1o or branch

    # Ensure a DimensionSet when the posting payload did not build one (so dimension_set_id can be backfilled).
    if dim_set is None and gl and gl.global_dimension_1_id and branch:
        from dimension.models import build_dimension_set_from_legacy, get_or_create_dimension_set

        dim_set = build_dimension_set_from_legacy(branch, g2_val, gl)
        if dim_set is None:
            dim_set = get_or_create_dimension_set({gl.global_dimension_1: branch})
    if dim_set is None and branch and dim is not None:
        from dimension.models import get_or_create_dimension_set

        dim_set = get_or_create_dimension_set({dim: branch})

    return out_branch, dim_set, None


def get_first_branch_dimension_value():
    """
    Returns the first branch DimensionValue for use as default.
    Prefer GeneralLedgerSetup.global_dimension_1 (Dimension) -> first DimensionValue by code.
    Fallback: Dimension with code "BRANCH" -> first DimensionValue by code.
    """
    try:
        from financials.models import GeneralLedgerSetup

        gl = GeneralLedgerSetup.objects.first()
        dim = None
        if gl and gl.global_dimension_1_id:
            dim = gl.global_dimension_1
        if not dim:
            dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        if not dim:
            return None
        return (
            DimensionValue.objects.filter(dimension_code=dim).order_by("code").first()
        )
    except Exception:
        return None
