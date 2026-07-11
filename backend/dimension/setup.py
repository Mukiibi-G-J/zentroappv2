"""
Tenant-safe defaults for dimensions and General Ledger Setup.

Used during company onboarding so G/L posting always has valid global dimensions.

Reuses existing BRANCH values when present; only creates a first value when none exist
(default ``MAIN`` / ``Main`` at company signup unless callers pass overrides).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, TypedDict

from django.utils.text import slugify

from postings import enums as posting_enums

logger = logging.getLogger(__name__)

BRANCH_DIMENSION_CODE = "BRANCH"
DEFAULT_FIRST_BRANCH_CODE = "MAIN"
DEFAULT_FIRST_BRANCH_DESCRIPTION = "Main"
# Alias kept for callers that referenced the old fallback name
FALLBACK_FIRST_BRANCH_CODE = DEFAULT_FIRST_BRANCH_CODE


class BranchSetupResult(TypedDict):
    branch_dimension: Any
    default_branch_value: Any


def suggest_branch_value_code_from_label(label: Optional[str]) -> Optional[str]:
    """
    Build a short, unique-friendly code from a human label (e.g. company address).
    Returns None if there is nothing usable (caller will use DEFAULT_FIRST_BRANCH_CODE).
    """
    if not label or not str(label).strip():
        return None
    raw = str(label).strip()
    s = slugify(raw)
    if not s:
        # e.g. only non-Latin chars: take alnum runs
        s = slugify(re.sub(r"\s+", "-", raw)[:120])
    if not s:
        return None
    return s[:80]


def _unique_dimension_value_code(base: str) -> str:
    from dimension.models import DimensionValue

    code = base[:255]
    if not DimensionValue.objects.filter(code=code).exists():
        return code
    n = 0
    while True:
        n += 1
        suffix = f"-{n}"
        candidate = (base[: (255 - len(suffix))] + suffix)[:255]
        if not DimensionValue.objects.filter(code=candidate).exists():
            return candidate


def ensure_dimension_has_values(dimension) -> None:
    """Ensure *dimension* has at least one DimensionValue (required for G/L entry validation)."""
    from dimension.models import DimensionValue

    if dimension is None:
        return
    if DimensionValue.objects.filter(dimension_code=dimension).exists():
        return
    base = (getattr(dimension, "code", None) or "DIM")[:80]
    code = _unique_dimension_value_code(f"{base}-DEFAULT")
    DimensionValue.objects.create(
        code=code,
        description=(
            f"Default – {getattr(dimension, 'description', None) or getattr(dimension, 'code', 'dimension')}"
        )[:255],
        dimension_type=posting_enums.DimensionType.Standard.value,
        dimension_code=dimension,
    )
    logger.info(
        "Created default dimension value %s for dimension %s",
        code,
        getattr(dimension, "code", dimension),
    )


def ensure_default_branch_dimension_and_gl_setup(
    *,
    default_branch_value_code: Optional[str] = None,
    default_branch_value_description: Optional[str] = None,
) -> BranchSetupResult:
    """
    Idempotent setup for tenants:

    - BRANCH dimension (get_or_create)
    - If **any** DimensionValue already exists for BRANCH → reuse the first (by code);
      **no new branch value is created**
    - If **none** exist → create one: use ``default_branch_value_code`` if given and unique,
      else ``MAIN`` (with uniqueness suffix if needed)
    - GeneralLedgerSetup with global_dimension_1 = BRANCH when unset
    - At least one DimensionValue for any other configured global dimensions (non-BRANCH)

    Call with the tenant schema active (e.g. inside ``schema_context``).
    """
    from dimension.models import Dimension, DimensionValue
    from financials.models import GeneralLedgerSetup

    branch_dim, _ = Dimension.objects.get_or_create(
        code=BRANCH_DIMENSION_CODE,
        defaults={"description": "Branch"},
    )

    existing = DimensionValue.objects.filter(dimension_code=branch_dim).order_by("code")
    if existing.exists():
        branch_value = existing.first()
        logger.debug(
            "Using existing BRANCH dimension value %s (no new branch row created)",
            branch_value.code,
        )
    else:
        desc_source = (default_branch_value_description or "").strip()
        desc = (desc_source or DEFAULT_FIRST_BRANCH_DESCRIPTION)[:255]

        code_candidate = (default_branch_value_code or "").strip()
        if code_candidate:
            code_candidate = code_candidate[:255]
            code_candidate = _unique_dimension_value_code(code_candidate)
        else:
            code_candidate = _unique_dimension_value_code(DEFAULT_FIRST_BRANCH_CODE)

        branch_value = DimensionValue.objects.create(
            code=code_candidate,
            description=desc,
            dimension_type=posting_enums.DimensionType.Standard.value,
            dimension_code=branch_dim,
        )
        logger.info("Created first BRANCH dimension value %s", code_candidate)

    gl = GeneralLedgerSetup.objects.first()
    if not gl:
        GeneralLedgerSetup.objects.create(global_dimension_1=branch_dim)
        logger.info("Created GeneralLedgerSetup with global_dimension_1=BRANCH")
    else:
        update_fields = []
        if not gl.global_dimension_1_id:
            gl.global_dimension_1 = branch_dim
            update_fields.append("global_dimension_1")
            logger.info("Set GeneralLedgerSetup.global_dimension_1 to BRANCH")
        if update_fields:
            gl.save(update_fields=update_fields)
        if gl.global_dimension_1_id:
            ensure_dimension_has_values(gl.global_dimension_1)
        if gl.global_dimension_2_id:
            ensure_dimension_has_values(gl.global_dimension_2)

    return {
        "branch_dimension": branch_dim,
        "default_branch_value": branch_value,
    }
