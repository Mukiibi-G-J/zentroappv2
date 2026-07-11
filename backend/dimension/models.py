import hashlib
from django.db import IntegrityError, models
from django.core.exceptions import ValidationError
from postings import enums
from base.models import BaseModel

# Create your models here.


class Dimension(BaseModel):
    code = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code}"


class DimensionValue(BaseModel):
    code = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255)
    dimension_type = models.CharField(
        max_length=255, choices=enums.DimensionType.choices
    )
    dimension_code = models.ForeignKey(
        Dimension,  # Now this reference will work since Dimension is defined first
        on_delete=models.SET_NULL,
        related_name="dimension_code",
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.code}"


class DimensionSet(BaseModel):
    """
    BC Table 480 equivalent: groups DimensionSetEntry rows. A dimension set is a
    unique combination of dimension values. Immutable - changes create new set.
    """

    # Optional: signature for O(1) lookup (hash of sorted dim_code:dim_value pairs)
    signature = models.CharField(
        max_length=64, unique=True, blank=True, null=True, db_index=True
    )

    class Meta:
        verbose_name = "Dimension Set"
        verbose_name_plural = "Dimension Sets"


class DimensionSetEntry(BaseModel):
    """
    BC Table 480 Dimension Set Entry: one row per (dimension_set, dimension_code).
    Stores which DimensionValue is selected for each Dimension in the set.
    """

    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    dimension_code = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name="dimension_set_entries",
    )
    dimension_value = models.ForeignKey(
        DimensionValue,
        on_delete=models.CASCADE,
        related_name="dimension_set_entries",
    )

    class Meta:
        verbose_name = "Dimension Set Entry"
        verbose_name_plural = "Dimension Set Entries"
        unique_together = ("dimension_set", "dimension_code")

    def clean(self):
        if self.dimension_value and self.dimension_code:
            if self.dimension_value.dimension_code_id != self.dimension_code_id:
                raise ValidationError(
                    {
                        "dimension_value": "Dimension value does not match dimension code."
                    }
                )


def _compute_dimension_set_signature(dimension_values):
    """
    Compute deterministic signature for dimension set lookup.
    Input: dict of {Dimension or dim_code: DimensionValue or dim_value_id}
    """
    pairs = []
    for dim, val in dimension_values.items():
        dim_id = dim.pk if hasattr(dim, "pk") else dim
        val_id = val.pk if hasattr(val, "pk") else val
        if dim_id is not None and val_id is not None:
            pairs.append((dim_id, val_id))
    pairs.sort(key=lambda x: (x[0], x[1]))
    content = "|".join(f"{d}:{v}" for d, v in pairs)
    return hashlib.sha256(content.encode()).hexdigest()


def get_or_create_dimension_set(dimension_values):
    """
    BC equivalent: find existing dimension set by exact combination, or create new.
    Input: {Dimension: DimensionValue} or {dimension_id: dimension_value_id}
    Dimension sets are immutable - never update, only create new.
    """
    if not dimension_values:
        return None

    # Normalize to Dimension and DimensionValue objects
    normalized = {}
    for dim, val in dimension_values.items():
        if val is None:
            continue
        dim_obj = dim if isinstance(dim, Dimension) else Dimension.objects.get(pk=dim)
        val_obj = (
            val
            if isinstance(val, DimensionValue)
            else DimensionValue.objects.get(pk=val)
        )
        if val_obj.dimension_code_id != dim_obj.pk:
            continue  # Skip if value doesn't belong to dimension
        normalized[dim_obj] = val_obj

    if not normalized:
        return None

    signature = _compute_dimension_set_signature(normalized)
    norm_set = {(d.pk, v.pk) for d, v in normalized.items()}
    entry_specs = sorted(normalized.items(), key=lambda x: x[0].code)

    def _attach_entries(dim_set):
        DimensionSetEntry.objects.bulk_create(
            [
                DimensionSetEntry(
                    dimension_set=dim_set,
                    dimension_code=dim,
                    dimension_value=val,
                )
                for dim, val in entry_specs
            ]
        )
        return dim_set

    existing = DimensionSet.objects.filter(signature=signature).first()
    if existing:
        entries = existing.entries.select_related("dimension_code", "dimension_value")
        entry_set = {(e.dimension_code_id, e.dimension_value_id) for e in entries}
        if entry_set == norm_set:
            return existing
        # Signature matches but entries are missing/corrupt (e.g. partial create).
        # Repair in place instead of inserting a duplicate signature row.
        existing.entries.all().delete()
        return _attach_entries(existing)

    from django.db import IntegrityError

    try:
        dim_set = DimensionSet.objects.create(signature=signature)
    except IntegrityError:
        existing = DimensionSet.objects.filter(signature=signature).first()
        if not existing:
            raise
        existing.entries.all().delete()
        return _attach_entries(existing)

    return _attach_entries(dim_set)


def get_dimension_value_from_set(dimension_set, dimension):
    """
    BC Shortcut Dim 3-8 equivalent: lookup DimensionValue for a Dimension in the set.
    """
    if dimension_set is None or dimension is None:
        return None
    dim = (
        dimension
        if isinstance(dimension, Dimension)
        else Dimension.objects.get(pk=dimension)
    )
    entry = (
        dimension_set.entries.filter(dimension_code=dim)
        .select_related("dimension_value")
        .first()
    )
    return entry.dimension_value if entry else None


def expand_dimension_set_to_dict(dimension_set):
    """
    Convert dimension set to {dimension_code: dimension_value} for merging.
    """
    if dimension_set is None:
        return {}
    entries = dimension_set.entries.select_related(
        "dimension_code", "dimension_value"
    ).all()
    return {e.dimension_code: e.dimension_value for e in entries}


def build_dimension_set_from_legacy(dimension_1, dimension_2, gl_setup):
    """
    For migration: build DimensionSet from legacy dimension_1/dimension_2 using
    GeneralLedgerSetup to map to Dimension types.
    """
    dim_values = {}
    if gl_setup and gl_setup.global_dimension_1_id and dimension_1:
        dim_values[gl_setup.global_dimension_1] = dimension_1
    if gl_setup and gl_setup.global_dimension_2_id and dimension_2:
        dim_values[gl_setup.global_dimension_2] = dimension_2
    if not dim_values:
        return None
    return get_or_create_dimension_set(dim_values)


def normalize_gl_entry_dimensions(entry_dict):
    """
    Convert legacy dimension_1/dimension_2 or global_dimension_1/global_dimension_2
    in gl_entry dict to dimension_set, global_dimension_1, global_dimension_2.
    Modifies dict in place, returns it.
    Merges any existing dimension_set with popped global/legacy dimensions.
    """
    dim_1 = entry_dict.pop("global_dimension_1", None) or entry_dict.pop(
        "dimension_1", None
    )
    dim_2 = entry_dict.pop("global_dimension_2", None) or entry_dict.pop(
        "dimension_2", None
    )
    dimension_set = entry_dict.get("dimension_set")

    if dim_1 is None and dim_2 is None:
        if dimension_set is not None:
            payload = get_posting_dimension_payload(dimension_set=dimension_set)
            entry_dict["dimension_set"] = payload["dimension_set"]
            entry_dict["global_dimension_1"] = payload["global_dimension_1"]
            entry_dict["global_dimension_2"] = payload["global_dimension_2"]
        else:
            entry_dict.setdefault("dimension_set", None)
            entry_dict.setdefault("global_dimension_1", None)
            entry_dict.setdefault("global_dimension_2", None)
        return entry_dict

    payload = get_posting_dimension_payload(
        global_dimension_1=dim_1,
        global_dimension_2=dim_2,
        dimension_set=dimension_set,
    )
    entry_dict["dimension_set"] = payload["dimension_set"]
    entry_dict["global_dimension_1"] = payload["global_dimension_1"]
    entry_dict["global_dimension_2"] = payload["global_dimension_2"]
    return entry_dict


def get_posting_dimension_payload(
    global_dimension_1=None,
    global_dimension_2=None,
    dimension_1=None,
    dimension_2=None,
    dimension_set=None,
    gl_setup=None,
):
    """
    Build dimension_set, global_dimension_1, global_dimension_2 for GL/ledger entry creation.
    Used by posting logic. Merges dimension_set (from line) with global_dimension_1/2 (from user).
    Accepts global_dimension_1/2 (preferred) or dimension_1/2 (legacy alias).
    """
    dim_1 = global_dimension_1 if global_dimension_1 is not None else dimension_1
    dim_2 = global_dimension_2 if global_dimension_2 is not None else dimension_2
    if gl_setup is None:
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
        except Exception:
            gl_setup = None
    dim_values = {}

    # Expand existing dimension_set
    if dimension_set:
        dim_values.update(expand_dimension_set_to_dict(dimension_set))

    # Override/merge with dim_1 (user branch, etc.)
    if dim_1 and gl_setup and gl_setup.global_dimension_1_id:
        dim_values[gl_setup.global_dimension_1] = dim_1
    elif dim_1 and gl_setup is None:
        # Fallback: try BRANCH dimension
        branch_dim = Dimension.objects.filter(code="BRANCH").first()
        if branch_dim:
            dim_values[branch_dim] = dim_1

    if dim_2 and gl_setup and gl_setup.global_dimension_2_id:
        dim_values[gl_setup.global_dimension_2] = dim_2

    # When G/L Setup mandates global dimensions but the line supplied none (e.g. API /
    # new tenant without branch on the request), default to the first DimensionValue
    # for each required dimension so posting does not 500 on model clean().
    if gl_setup:
        if gl_setup.global_dimension_1_id:
            g1_dim = gl_setup.global_dimension_1
            if g1_dim not in dim_values:
                dv = (
                    DimensionValue.objects.filter(dimension_code=g1_dim)
                    .order_by("code")
                    .first()
                )
                if dv:
                    dim_values[g1_dim] = dv
        if gl_setup.global_dimension_2_id:
            g2_dim = gl_setup.global_dimension_2
            if g2_dim not in dim_values:
                dv2 = (
                    DimensionValue.objects.filter(dimension_code=g2_dim)
                    .order_by("code")
                    .first()
                )
                if dv2:
                    dim_values[g2_dim] = dv2

    if not dim_values:
        return {
            "dimension_set": None,
            "global_dimension_1": None,
            "global_dimension_2": None,
        }

    dim_set = get_or_create_dimension_set(dim_values)
    global_1 = (
        get_dimension_value_from_set(dim_set, gl_setup.global_dimension_1)
        if gl_setup and gl_setup.global_dimension_1_id
        else None
    )
    global_2 = (
        get_dimension_value_from_set(dim_set, gl_setup.global_dimension_2)
        if gl_setup and gl_setup.global_dimension_2_id
        else None
    )
    if not global_1 and dim_1:
        global_1 = dim_1
    if not global_2 and dim_2:
        global_2 = dim_2
    return {
        "dimension_set": dim_set,
        "global_dimension_1": global_1,
        "global_dimension_2": global_2,
    }


def get_default_dimension_value():
    """
    Default to the first DimensionValue.
    This keeps existing tenants working while defaults are configured.
    """
    return DimensionValue.objects.order_by("code").first()


def resolve_dimension_value(value):
    """
    Resolve DimensionValue from id (int), code (str), or DimensionValue instance.
    Use when accepting dimension_1 from API payloads that may send either.
    """
    if value is None:
        return None
    if isinstance(value, DimensionValue):
        return value
    if isinstance(value, int):
        try:
            return DimensionValue.objects.get(pk=value)
        except DimensionValue.DoesNotExist:
            return None
    if isinstance(value, str) and value.strip():
        try:
            return DimensionValue.objects.get(code=value.strip())
        except DimensionValue.DoesNotExist:
            return None
    return None


def get_default_dimensions_for_entity(related_model, no):
    """
    Returns {Dimension: DimensionValue} for the given entity (BC-style default dimensions).

    Args:
        related_model: Full model path, e.g. 'sales.Customer', 'items.Item', 'purchases.Vendor'
        no: Entity identifier (customer.no, item.no, vendor.no)

    Returns:
        Dict mapping Dimension to DimensionValue, empty dict if no defaults or entity not found.
    """
    if not no or not related_model:
        return {}
    try:
        from base.models import Objects

        table_obj = Objects.objects.filter(
            object_type="Table", related_model=related_model
        ).first()
        if not table_obj:
            return {}
        default_dims = DefaultDimension.objects.filter(
            table=table_obj,
            no=str(no),
        ).select_related("dimension_code", "dimension_value")
        return {dim.dimension_code: dim.dimension_value for dim in default_dims}
    except Exception:
        return {}


def merge_dimension_defaults(*sources):
    """
    Merge dimension dicts; later sources override earlier for same Dimension.
    Input: each source is {Dimension: DimensionValue}. Returns merged dict.
    """
    merged = {}
    for source in sources:
        if source:
            merged.update(source)
    return merged


def header_dimensions_to_dict(header):
    """
    Convert a document header (with global_dimension_1, global_dimension_2, dimension_set)
    into {Dimension: DimensionValue} for merging. Header can be a model instance.
    """
    if header is None:
        return {}
    result = {}
    if getattr(header, "dimension_set", None):
        result.update(expand_dimension_set_to_dict(header.dimension_set))
    dim_1 = getattr(header, "global_dimension_1", None)
    if dim_1 and dim_1.dimension_code_id:
        result[dim_1.dimension_code] = dim_1
    dim_2 = getattr(header, "global_dimension_2", None)
    if dim_2 and dim_2.dimension_code_id:
        result[dim_2.dimension_code] = dim_2
    return result


def update_global_dim_from_dimension_set(instance):
    """
    BC-style: Given a header with dimension_set, derive global_dimension_1 and
    global_dimension_2 from the set using GeneralLedgerSetup. Sets attributes
    on instance; does not save.
    """
    try:
        from financials.models import GeneralLedgerSetup
    except Exception:
        return
    gl_setup = GeneralLedgerSetup.objects.first()
    if not gl_setup:
        return
    dim_set = getattr(instance, "dimension_set", None)
    if not dim_set:
        return
    if gl_setup.global_dimension_1_id:
        val = get_dimension_value_from_set(dim_set, gl_setup.global_dimension_1)
        setattr(instance, "global_dimension_1_id", val.id if val else None)
    if gl_setup.global_dimension_2_id:
        val = get_dimension_value_from_set(dim_set, gl_setup.global_dimension_2)
        setattr(instance, "global_dimension_2_id", val.id if val else None)


def validate_shortcut_dimension_value(instance, field_number, value):
    """
    BC-style: When global_dimension_1 (1) or global_dimension_2 (2) changes,
    merge the new value into the current dimension set and assign to
    instance.dimension_set. Does not save.
    """
    try:
        from financials.models import GeneralLedgerSetup
    except Exception:
        return
    gl_setup = GeneralLedgerSetup.objects.first()
    if not gl_setup:
        return
    dim = None
    if field_number == 1 and gl_setup.global_dimension_1_id:
        dim = gl_setup.global_dimension_1
    elif field_number == 2 and gl_setup.global_dimension_2_id:
        dim = gl_setup.global_dimension_2
    if not dim:
        return
    dim_val = resolve_dimension_value(value)
    if not dim_val or dim_val.dimension_code_id != dim.pk:
        return
    current_dict = {}
    if getattr(instance, "dimension_set", None):
        current_dict = expand_dimension_set_to_dict(instance.dimension_set)
    current_dict[dim] = dim_val
    new_set = get_or_create_dimension_set(current_dict)
    if new_set:
        instance.dimension_set = new_set
        setattr(instance, "global_dimension_1_id", None)
        setattr(instance, "global_dimension_2_id", None)
        update_global_dim_from_dimension_set(instance)


def get_delta_dimension_set(
    line_dim_set, new_parent_dim_set, old_parent_dim_set, gl_setup
):
    """
    BC-style GetDeltaDimSetID: merge line's dimension set with parent's new set.
    Parent dimensions override overlapping dimensions. Returns DimensionSet or None.
    """
    line_dict = expand_dimension_set_to_dict(line_dim_set) if line_dim_set else {}
    new_parent_dict = (
        expand_dimension_set_to_dict(new_parent_dim_set) if new_parent_dim_set else {}
    )
    old_parent_dict = (
        expand_dimension_set_to_dict(old_parent_dim_set) if old_parent_dim_set else {}
    )
    merged = dict(line_dict)
    for dim, val in new_parent_dict.items():
        merged[dim] = val
    for dim in old_parent_dict:
        if dim in new_parent_dict:
            continue
        if dim in merged:
            merged.pop(dim, None)
    if not merged:
        return None
    return get_or_create_dimension_set(merged)


def update_all_line_dim(header, new_dim_set_id, old_dim_set_id):
    """
    BC-style UpdateAllLineDim: for each PurchaseInvoiceLine of the header,
    compute new line dimension set via get_delta_dimension_set, set
    line.dimension_set and line.global_dimension_1, then save.
    """
    from purchases.models import PurchaseInvoiceLine

    if not hasattr(header, "lines"):
        return
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
    except Exception:
        gl_setup = None
    new_parent = None
    if new_dim_set_id:
        new_parent = DimensionSet.objects.filter(pk=new_dim_set_id).first()
    old_parent = None
    if old_dim_set_id:
        old_parent = DimensionSet.objects.filter(pk=old_dim_set_id).first()
    for line in header.lines.all():
        new_line_set = get_delta_dimension_set(
            line.dimension_set, new_parent, old_parent, gl_setup
        )
        if new_line_set:
            line.dimension_set = new_line_set
            if gl_setup and gl_setup.global_dimension_1_id:
                gd1 = get_dimension_value_from_set(
                    new_line_set, gl_setup.global_dimension_1
                )
                line.global_dimension_1 = gd1
        else:
            line.dimension_set = None
            line.global_dimension_1 = None
        line.save()


def get_merged_line_dimensions(
    customer_no=None,
    vendor_no=None,
    item=None,
    resource=None,
    request_user=None,
    line_data=None,
    header_dimensions=None,
):
    """
    BC-style merge: Header -> Customer/Vendor defaults -> Item/Resource defaults -> User -> Explicit line_data.
    Returns dict with dimension_set and global_dimension_1 for the line.
    For sales: pass customer_no, item or resource.
    For purchases: pass vendor_no, item.
    header_dimensions: optional {Dimension: DimensionValue} or header model instance with dimension fields.
    """
    try:
        from financials.models import GeneralLedgerSetup
    except Exception:
        GeneralLedgerSetup = None

    # Header dimensions as first source (highest priority when present)
    header_dims = {}
    if header_dimensions is not None:
        if isinstance(header_dimensions, dict):
            header_dims = header_dimensions
        else:
            header_dims = header_dimensions_to_dict(header_dimensions)

    header_defaults = {}
    if customer_no:
        header_defaults = get_default_dimensions_for_entity(
            "sales.Customer", customer_no
        )
    elif vendor_no:
        header_defaults = get_default_dimensions_for_entity(
            "purchases.Vendor", vendor_no
        )

    line_entity_defaults = {}
    if item and getattr(item, "no", None):
        line_entity_defaults = get_default_dimensions_for_entity("items.Item", item.no)
    elif resource and getattr(resource, "code", None):
        dim_val = getattr(resource, "global_dimension_1", None)
        if dim_val and dim_val.dimension_code_id:
            line_entity_defaults = {dim_val.dimension_code: dim_val}

    user_dim = {}
    if request_user and getattr(request_user, "global_dimension_1", None):
        uv = request_user.global_dimension_1
        if uv and uv.dimension_code_id:
            user_dim = {uv.dimension_code: uv}

    explicit_dim = {}
    if line_data:
        if line_data.get("dimension_set_id"):
            ds = DimensionSet.objects.filter(pk=line_data["dimension_set_id"]).first()
            if ds:
                explicit_dim = expand_dimension_set_to_dict(ds)
        elif line_data.get("dimensions") and isinstance(
            line_data.get("dimensions"), dict
        ):
            for dim_code, dim_val_id in line_data["dimensions"].items():
                dim = Dimension.objects.filter(code=dim_code).first()
                if dim and dim_val_id:
                    dv = (
                        DimensionValue.objects.filter(pk=dim_val_id).first()
                        if isinstance(dim_val_id, int)
                        else DimensionValue.objects.filter(code=str(dim_val_id)).first()
                    )
                    if dv and dv.dimension_code_id == dim.pk:
                        explicit_dim[dim] = dv
        if (
            line_data.get("global_dimension_1") is not None
            or line_data.get("dimension_1") is not None
        ):
            dv = resolve_dimension_value(
                line_data.get("global_dimension_1") or line_data.get("dimension_1")
            )
            if dv and dv.dimension_code_id:
                explicit_dim[dv.dimension_code] = dv

    merged = merge_dimension_defaults(
        header_dims, header_defaults, line_entity_defaults, user_dim, explicit_dim
    )
    if not merged:
        return {"dimension_set": None, "global_dimension_1": None}

    dim_set = get_or_create_dimension_set(merged)
    if not dim_set:
        return {"dimension_set": None, "global_dimension_1": None}
    gl_setup = GeneralLedgerSetup.objects.first() if GeneralLedgerSetup else None
    payload = get_posting_dimension_payload(dimension_set=dim_set, gl_setup=gl_setup)
    return {
        "dimension_set": payload.get("dimension_set"),
        "global_dimension_1": payload.get("global_dimension_1"),
    }


class DefaultDimension(BaseModel):
    class ValuePosting(models.TextChoices):
        NONE = "none", "None"
        CODE_MANDATORY = "code_mandatory", "Code Mandatory"
        SAME_CODE = "same_code", "Same Code"

    table = models.ForeignKey(
        "base.Objects",
        on_delete=models.CASCADE,
        related_name="default_dimensions",
        limit_choices_to={"object_type": "Table"},
        help_text="Target table for default dimension",
    )
    no = models.CharField(
        max_length=255,
        help_text="Record identifier (e.g., item no, customer no, location code)",
    )
    dimension_code = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name="default_dimensions",
        help_text="Dimension code (e.g., BRANCH)",
    )
    dimension_value = models.ForeignKey(
        DimensionValue,
        on_delete=models.CASCADE,
        related_name="default_dimensions",
        help_text="Dimension value (e.g., Ntinda)",
        default=get_default_dimension_value,
    )
    value_posting = models.CharField(
        max_length=20,
        choices=ValuePosting.choices,
        default=ValuePosting.NONE,
        help_text="Default dimension value posting rule",
    )
    table_caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional table caption for display",
    )

    class Meta:
        verbose_name = "Default Dimension"
        verbose_name_plural = "Default Dimensions"
        unique_together = ("table", "no", "dimension_code")
        indexes = [
            models.Index(fields=["table", "no"]),
            models.Index(fields=["dimension_code", "dimension_value"]),
        ]

    def clean(self):
        # Use _id to avoid RelatedObjectDoesNotExist when dimension_code is empty (e.g. formset empty row)
        if self.dimension_code_id and self.dimension_value_id:
            if self.dimension_value.dimension_code_id != self.dimension_code_id:
                raise ValidationError(
                    {
                        "dimension_value": "Dimension value does not match dimension code."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class DimensionBackfillAudit(models.Model):
    """
    One row per row touched by the branch / dimension set backfill migration, for rollback.
    """

    app_label = models.CharField(max_length=100, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.BigIntegerField()
    prev_global_dimension_1_id = models.IntegerField(null=True, blank=True)
    prev_global_dimension_2_id = models.IntegerField(null=True, blank=True)
    prev_dimension_set_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dimension_backfill_audit"
        indexes = [
            models.Index(
                fields=["app_label", "model_name", "object_id"],
                name="dimension_b_app_lab_585f37_idx",
            ),
        ]
