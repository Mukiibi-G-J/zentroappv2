from celery import shared_task
import pandas as pd
from django.db import transaction
from django.core.cache import cache
import os
from django.core.files.storage import default_storage
from django.conf import settings
from celery.states import PENDING, SUCCESS, FAILURE, STARTED
from celery.utils.log import get_task_logger
from celery import current_task
from django_tenants.utils import schema_context
from django.db import connection
from django.core.exceptions import ValidationError
from datetime import datetime
from authentication.models import CustomUser as User
import logging
from io import BytesIO
from typing import List, Optional, Any, Dict

from items.models import (
    Item,
    UnitOfMeasure,
    ItemCategory,
    ItemJournal,
    ItemLedgerEntries,
    TrackingSpecification,
    ValueEntry,
)
from postings.models import GeneralProductPostingGroup, InventoryPostingGroup
from items.enums import InventoryType, CostingMethod
from reports.utils.formatters import format_currency
import base64

logger = logging.getLogger(__name__)


def _pick_fifo_lot_candidate(candidates, required_base_qty, preferred_lot_no=None):
    """
    Pick a lot candidate with enough quantity using FIFO ordering.
    candidates: list of dicts with keys lot_no, expiry_date, available_qty, first_seen
    """
    required = int(required_base_qty or 0)
    if required <= 0:
        return None

    if preferred_lot_no:
        preferred = [
            c
            for c in candidates
            if (c.get("lot_no") or "").strip().lower()
            == preferred_lot_no.strip().lower()
        ]
        if preferred:
            chosen = preferred[0]
            if int(chosen.get("available_qty") or 0) >= required:
                return chosen
            return None

    for c in candidates:
        if int(c.get("available_qty") or 0) >= required:
            return c
    return None


def _resolve_unit_amount_for_import(
    *,
    raw_unit_amount,
    raw_unit_cost=None,
    lot_entry,
    item,
):
    """Resolve unit amount for import; keep provided value, else derive from lot/item."""
    from items.models import money_decimal

    if raw_unit_amount is not None and str(raw_unit_amount).strip() != "":
        return money_decimal(raw_unit_amount)

    if raw_unit_cost is not None and str(raw_unit_cost).strip() != "":
        return money_decimal(raw_unit_cost)

    # Prefer lot-specific latest value entry cost-per-unit.
    if lot_entry is not None:
        ve = (
            ValueEntry.objects.filter(item_ledger_entry_no=lot_entry)
            .order_by("-posting_date", "-created_at")
            .first()
        )
        if ve and ve.cost_per_unit is not None:
            return money_decimal(ve.cost_per_unit)

    if getattr(item, "unit_cost", None) is not None:
        return money_decimal(item.unit_cost)
    if getattr(item, "unit_price", None) is not None:
        return money_decimal(item.unit_price)

    return None


def _build_import_lot_no(item_no, row_index):
    """
    Generate a cleaner lot number for import-created lots.
    Example: IMP-000605-20260507-0072
    """
    item_suffix = str(item_no or "").replace("ITM-", "").replace("ITM", "").strip()
    item_suffix = item_suffix or "ITEM"
    stamp = datetime.now().strftime("%Y%m%d")
    return f"IMP-{item_suffix}-{stamp}-{int(row_index):04d}"

def _post_item_journal_ids(
    *,
    journal_ids: List[int],
    user: User,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Post item journals using the same preview/post pipeline as the API view.
    Returns { posted_ids, invalid_journals }.
    """
    from django.test.client import RequestFactory
    from django.contrib.messages.storage.base import BaseStorage
    from django.contrib.messages import constants
    from django.utils import timezone
    import uuid
    from items.models import ItemJournal
    from items.admin import ItemJournalPreviewProcessor
    from items.posting import ItemJournalFinalPoster

    rf = RequestFactory()
    request = rf.post("/api/item-journal/post-async")
    request.user = user
    if branch_id:
        request.META["HTTP_X_BRANCH_ID"] = str(branch_id)

    class ValidationMessageStorage(BaseStorage):
        def __init__(self, request):
            super().__init__(request)
            self.validation_errors = []

        def add(self, level, message, extra_tags=""):
            if level == constants.ERROR:
                self.validation_errors.append(str(message))

        def _get(self, *args, **kwargs):
            return [], True

        def _store(self, messages, response, *args, **kwargs):
            return []

    invalid_journals = []
    posted_ids: List[int] = []

    for journal_id in journal_ids:
        journalentry = ItemJournal.objects.get(pk=journal_id)
        receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        original_messages = getattr(request, "_messages", None)
        validation_storage = ValidationMessageStorage(request)
        request._messages = validation_storage
        try:
            previewer = ItemJournalPreviewProcessor(journalentry, request, receipt_no=receipt_no)
            preview_data = previewer.process()
        finally:
            if original_messages is not None:
                request._messages = original_messages
            elif hasattr(request, "_messages"):
                delattr(request, "_messages")

        validation_errors = validation_storage.validation_errors
        if not preview_data or (isinstance(preview_data, dict) and not any(preview_data.values())):
            invalid_journals.append(
                {"id": journalentry.id, "document_no": journalentry.document_no, "errors": validation_errors}
            )
            continue

        poster = ItemJournalFinalPoster(preview_data, journalentry, user)
        try:
            poster.post_to_tables()
            posted_ids.append(journalentry.id)
        except Exception as e:
            invalid_journals.append(
                {"id": journalentry.id, "document_no": journalentry.document_no, "errors": [str(e)]}
            )

    return {"posted_ids": posted_ids, "invalid_journals": invalid_journals}


@shared_task(bind=True)
def post_item_journals_async(
    self,
    journal_ids=None,
    schema_name=None,
    user_id=None,
    branch_id=None,
):
    """
    Post item journals in the background (Celery).
    Returns progress updates compatible with /company/task-status/<task_id>/.
    """
    logger = get_task_logger(__name__)
    journal_ids = journal_ids or []
    total = len(journal_ids)

    try:
        schema_name = schema_name or settings.PUBLIC_SCHEMA_NAME
        with schema_context(schema_name):
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    user = None
            if not user:
                user = User.objects.filter(is_superuser=True).first()
            if not user:
                raise ValidationError("No valid user found for posting")

            posted: List[int] = []
            invalid: List[Dict[str, Any]] = []

            # Post one-by-one to keep validation error granularity, but report progress every few rows.
            for idx, jid in enumerate(journal_ids):
                result = _post_item_journal_ids(
                    journal_ids=[int(jid)],
                    user=user,
                    branch_id=int(branch_id) if branch_id else None,
                )
                posted.extend(result["posted_ids"])
                invalid.extend(result["invalid_journals"])

                if idx % 5 == 0 or idx == total - 1:
                    progress = int(((idx + 1) / total) * 100) if total else 100
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": progress,
                            "message": f"Posting journals... ({idx + 1}/{total})",
                            "status": "processing",
                            "posted_count": len(posted),
                            "failed_count": len(invalid),
                        },
                    )

            success = len(invalid) == 0
            return {
                "progress": 100,
                "message": "Posting completed" if success else "Posting completed with issues",
                "status": "success" if success else "failure",
                "posted_count": len(posted),
                "failed_count": len(invalid),
                "invalid_journals": invalid,
            }
    except Exception as e:
        logger.exception("post_item_journals_async failed")
        return {
            "progress": 0,
            "message": str(e),
            "status": "failure",
            "error": str(e),
        }


def _get_default_item_journal_template_batch():
    """Return (template, batch) for ITEM inventory adjustments."""
    from items.models import ItemJournalTemplate, ItemJournalBatch

    default_template, _ = ItemJournalTemplate.objects.get_or_create(
        name="ITEM",
        defaults={"description": "Item Journal", "type": "item"},
    )
    default_batch, _ = ItemJournalBatch.objects.get_or_create(
        journal_template=default_template,
        name="DEFAULT",
        defaults={"description": "Default Journal"},
    )
    try:
        from setup.models import InventorySetup

        inv_setup = InventorySetup.objects.all().first()
        series = getattr(inv_setup, "item_journal_no_series", None) if inv_setup else None
        if series:
            if not default_template.no_series_id:
                default_template.no_series = series
                default_template.save(update_fields=["no_series"])
            if not default_batch.no_series_id:
                default_batch.no_series = series
                default_batch.save(update_fields=["no_series"])
    except Exception:
        pass
    return default_template, default_batch


def _resolve_import_dim_payload(user, branch_id):
    from dimension.models import get_posting_dimension_payload, DimensionValue

    branch_value = None
    if branch_id:
        try:
            branch_value = DimensionValue.objects.filter(pk=int(branch_id)).first()
        except Exception:
            branch_value = None
    if not branch_value and user:
        branch_value = getattr(user, "global_dimension_1", None)
    return get_posting_dimension_payload(global_dimension_1=branch_value)


def _parse_row_quantity(row):
    raw_qty = _row_value(
        row,
        "Quantity",
        "quantity",
        "Qty",
        "Opening Quantity",
    )
    if raw_qty is None or (isinstance(raw_qty, str) and not str(raw_qty).strip()):
        return 0
    try:
        return int(float(raw_qty))
    except (TypeError, ValueError):
        return 0


def _row_value(row, *keys):
    """Return the first non-empty value for any of the given column headers."""
    for key in keys:
        if key in row.index if hasattr(row, "index") else key in row:
            val = row.get(key)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                if isinstance(val, str) and not val.strip():
                    continue
                return val
        # Case-insensitive fallback for renamed template headers
        if hasattr(row, "index"):
            for col in row.index:
                if str(col).strip().lower() == str(key).strip().lower():
                    val = row.get(col)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        if isinstance(val, str) and not val.strip():
                            continue
                        return val
    return None


def _create_opening_balance_journal_from_item_import(
    *,
    item,
    row,
    row_index,
    user,
    branch_id,
    stats,
    warnings,
):
    """
    Create an open positive adjustment journal for opening balance from item import.
    Returns document_no string on success, None if skipped.
    """
    from items.models import ItemUnitOfMeasure as ItemUOM
    from items.models import Location as Loc

    quantity = _parse_row_quantity(row)
    if quantity <= 0:
        return None

    type_raw = str(row.get("Type", row.get("type", ""))).strip() or "Inventory"
    if type_raw.lower() != "inventory":
        warnings.append(
            f"Row {row_index}: Quantity ignored for non-Inventory type '{type_raw}'."
        )
        return None

    item = Item.objects.filter(pk=item.pk).first() or item
    if not item:
        raise ValueError("Item not found after import")

    default_template, default_batch = _get_default_item_journal_template_batch()
    dim_payload = _resolve_import_dim_payload(user, branch_id)

    location = None
    if dim_payload.get("global_dimension_1") is not None:
        branch_code = getattr(dim_payload.get("global_dimension_1"), "code", "")
        if branch_code:
            location = Loc.objects.filter(code__iexact=branch_code).first()
            if not location:
                raise ValidationError(
                    f"No Location found for branch {branch_code!r}. "
                    "Add a Location whose code matches the branch code."
                )

    uom_raw = str(row.get("Unit of Measure", row.get("Unit Of Measure", ""))).strip()
    item_uom = None
    if uom_raw:
        uom_obj = UnitOfMeasure.objects.filter(code__iexact=uom_raw).first()
        if uom_obj:
            item_uom, _ = ItemUOM.objects.get_or_create(
                item=item,
                unit_of_measure=uom_obj,
                defaults={"quantity_per_unit": 1},
            )
    if not item_uom:
        item_uom = (
            ItemUOM.objects.filter(item=item, default=True).first()
            or ItemUOM.objects.filter(item=item).order_by("id").first()
        )

    qty_per_uom = int(getattr(item_uom, "quantity_per_unit", 1) or 1) if item_uom else 1
    required_base_qty = int(quantity) * qty_per_uom
    posting_date = datetime.now().date()
    desc = str(
        _row_value(row, "Description", "description") or ""
    ).strip()
    unit_cost_raw = _row_value(
        row,
        "Unit Cost",
        "unit_cost",
        "Unit Cost (Purchase)",
        "Purchase Price",
        "Cost Price",
        "Buying Price",
    )
    unit_price_raw = _row_value(
        row,
        "Unit Price",
        "unit_price",
        "Unit Price (Selling)",
        "Selling Price",
        "Sale Price",
    )
    raw_unit_amount = (
        unit_cost_raw
        if unit_cost_raw is not None and str(unit_cost_raw).strip() != ""
        else unit_price_raw
    )

    tracking = item.tracking_code
    raw_lot = ""
    exp_date = None
    selected_lot_entry = None

    if tracking and location:
        lot_qs = ItemLedgerEntries.objects.filter(item=item, location=location)
        if dim_payload.get("global_dimension_1") is not None:
            lot_qs = lot_qs.filter(
                global_dimension_1=dim_payload.get("global_dimension_1")
            )
        lot_qs = lot_qs.exclude(lot_no__isnull=True).exclude(lot_no="")
        lot_rows = list(
            lot_qs.values("lot_no", "expiry_date", "created_at", "remaining_quantity").order_by(
                "created_at", "id"
            )
        )
        lot_candidates_map = {}
        for row_lot in lot_rows:
            lot_key = row_lot.get("lot_no")
            if not lot_key:
                continue
            if lot_key not in lot_candidates_map:
                lot_candidates_map[lot_key] = {
                    "lot_no": lot_key,
                    "expiry_date": row_lot.get("expiry_date"),
                    "first_seen": row_lot.get("created_at"),
                }
        lot_candidates = sorted(
            lot_candidates_map.values(), key=lambda c: c.get("first_seen")
        )
        candidate = lot_candidates[0] if lot_candidates else None
        if candidate is None:
            raw_lot = _build_import_lot_no(item.no, row_index)
            exp_date = posting_date
        else:
            raw_lot = candidate.get("lot_no") or ""
            exp_date = candidate.get("expiry_date") or posting_date
        if raw_lot:
            selected_lot_entry = (
                lot_qs.filter(lot_no=raw_lot).order_by("created_at", "id").first()
            )

    journal_data = {
        "item": item,
        "entry_type": "PositiveAdjustment",
        "description": desc or f"Opening balance import — {item.item_name}",
        "quantity": quantity,
        "date": posting_date,
        "user": user,
        "adjustment_type": "opening_balance",
        "journal_template": default_template,
        "journal_batch": default_batch,
        "global_dimension_1": dim_payload.get("global_dimension_1"),
        "global_dimension_2": dim_payload.get("global_dimension_2"),
        "dimension_set": dim_payload.get("dimension_set"),
    }
    if item_uom:
        journal_data["item_unit_of_measure"] = item_uom
    if location:
        journal_data["location_code"] = location

    resolved_unit_amount = _resolve_unit_amount_for_import(
        raw_unit_amount=raw_unit_amount,
        raw_unit_cost=unit_cost_raw,
        lot_entry=selected_lot_entry,
        item=item,
    )
    if resolved_unit_amount is None:
        raise ValidationError(
            f"Unable to resolve Unit Amount for item '{item.item_name}'."
        )
    journal_data["unit_amount"] = resolved_unit_amount
    journal_data["unit_cost"] = resolved_unit_amount

    journal = ItemJournal.objects.create(**journal_data)
    stats["journals_created"] = stats.get("journals_created", 0) + 1
    doc_no = journal.document_no or str(journal.id)
    stats.setdefault("journal_document_nos", []).append(doc_no)

    if tracking and (raw_lot or exp_date is not None):
        if not location:
            raise ValidationError(
                "Location is required when item has lot/expiry tracking."
            )
        reqs = item.requires_tracking_line if tracking else {}
        if reqs.get("lot_no") and not raw_lot:
            raw_lot = _build_import_lot_no(item.no, row_index)
        if reqs.get("expiry_date") and exp_date is None:
            exp_date = posting_date

        spec_desc = (desc or f"Item import opening balance — {doc_no}")[:255]
        spec = TrackingSpecification(
            item=item,
            location_code=location,
            serial_no=None,
            lot_no=raw_lot or None,
            expiry_date=exp_date,
            quantity_base=required_base_qty,
            item_journal=journal,
            source_template=journal.journal_template,
            source_batch=journal.journal_batch,
            description=spec_desc,
            user=user,
        )
        spec.save()
        journal.item_specification = spec
        journal.save(update_fields=["item_specification"])

    return doc_no


@shared_task(bind=True)
def process_item_import(
    self,
    df_json=None,
    schema_name=None,
    file_path=None,
    user_id=None,
    branch_id=None,
    import_mode="standard",
):
    """
    Process item import from DataFrame JSON or an Excel file path.
    Args:
        self: Task instance
        df_json (str|None): JSON string of DataFrame (legacy config-package flow)
        schema_name (str): Schema name for tenant
        file_path (str|None): Path to uploaded Excel file (simple-import flow)
        user_id: User who initiated import (for opening balance journals)
        branch_id: Branch dimension id from request
        import_mode: 'standard' or 'opening_balance'
    """
    logger = get_task_logger(__name__)

    try:
        schema_name = schema_name or settings.PUBLIC_SCHEMA_NAME
        import_mode = (import_mode or "standard").strip().lower()
        if import_mode not in ("standard", "opening_balance"):
            import_mode = "standard"

        if file_path:
            df = pd.read_excel(file_path, header=0)
            df.columns = df.columns.str.strip()
            try:
                os.remove(file_path)
            except OSError:
                pass
        elif df_json:
            df = pd.read_json(df_json, orient="records")
        else:
            return {
                "success": False,
                "message": "No data provided (need file_path or df_json)",
                "status": "failed",
                "progress": 0,
            }

        with schema_context(schema_name):
            return _process_items(
                self,
                df,
                user_id=user_id,
                branch_id=branch_id,
                import_mode=import_mode,
            )
    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Import failed: {str(e)}",
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }


def _process_items(task, df, user_id=None, branch_id=None, import_mode="standard"):
    """Helper function to process items from DataFrame"""
    df = df.fillna("")
    total_rows = len(df)
    processed = 0
    stats = {
        "items_created": 0,
        "items_updated": 0,
        "units_created": 0,
        "categories_created": 0,
        "journals_created": 0,
        "journal_document_nos": [],
    }
    row_errors = []
    warnings = []

    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.filter(is_superuser=True).first()

    import_mode = (import_mode or "standard").strip().lower()

    _update_task_status(task, 0, 0, total_rows, "Starting import...")

    for index, row in df.iterrows():
        row_num = index + 2
        try:
            item = _process_single_item(row, stats)
            processed += 1

            raw_qty = _parse_row_quantity(row)
            if import_mode == "standard" and raw_qty > 0:
                warnings.append(
                    f"Row {row_num}: Quantity column ignored (standard import mode)."
                )
            elif import_mode == "opening_balance" and item and user:
                try:
                    _create_opening_balance_journal_from_item_import(
                        item=item,
                        row=row,
                        row_index=row_num,
                        user=user,
                        branch_id=branch_id,
                        stats=stats,
                        warnings=warnings,
                    )
                except Exception as journal_exc:
                    row_errors.append(f"Row {row_num}: {journal_exc}")
                    logger.error(
                        f"Opening balance journal error row {row_num}: {journal_exc}",
                        exc_info=True,
                    )

            if processed % 10 == 0:
                _update_task_status(
                    task,
                    processed,
                    stats["items_updated"],
                    total_rows,
                    f"Processing row {processed} of {total_rows}",
                )

        except Exception as e:
            row_errors.append(f"Row {row_num}: {str(e)}")
            logger.error(f"Error on row {row_num}: {str(e)}", exc_info=True)
            continue

    all_errors = row_errors + warnings

    return {
        "success": True,
        "message": "Import completed successfully",
        "status": "completed",
        "progress": 100,
        "items_created": stats["items_created"],
        "items_updated": stats["items_updated"],
        "units_created": stats["units_created"],
        "categories_created": stats["categories_created"],
        "journals_created": stats.get("journals_created", 0),
        "journal_document_nos": stats.get("journal_document_nos", []),
        "total_rows": total_rows,
        "failed_count": len(row_errors),
        "errors": all_errors if all_errors else [],
        "warnings": warnings,
    }


def _process_single_item(row, stats):
    """Process a single item row from either the simple template or the config-package template."""
    # Support both column naming conventions
    item_name = str(row.get("Item Name", row.get("item_name", ""))).strip()
    if not item_name:
        raise ValueError("Item Name is required")

    uom_raw = str(row.get("Unit of Measure", row.get("Unit Of Measure", ""))).strip()
    category_raw = str(row.get("Item Category", row.get("item_category", ""))).strip()
    type_raw = str(row.get("Type", row.get("type", ""))).strip() or "Inventory"
    unit_price_raw = _row_value(
        row,
        "Unit Price",
        "unit_price",
        "Unit Price (Selling)",
        "Selling Price",
        "Sale Price",
    )
    # Optional purchase/cost on the item card when provided in the template
    unit_cost_item_raw = _row_value(
        row,
        "Unit Cost",
        "unit_cost",
        "Unit Cost (Purchase)",
        "Purchase Price",
        "Cost Price",
        "Buying Price",
    )
    bar_code_raw = str(row.get("Bar Code No", row.get("bar_code_no", ""))).strip()
    description_raw = str(row.get("Description", row.get("description", ""))).strip()
    shelf_no_raw = str(row.get("Shelf No", row.get("shelf_no", row.get("Self No", "")))).strip()

    # --- Legacy columns (config-package template) ---
    gen_posting_raw = str(row.get("General Product Posting Group", "")).strip()
    inv_posting_raw = str(row.get("Inventory Posting Group", "")).strip()
    costing_raw = str(row.get("Costing Method", "")).strip()
    blocked_raw = row.get("Blocked", False)

    # UOM
    unit = None
    if uom_raw:
        unit, unit_created = UnitOfMeasure.objects.get_or_create(
            code=uom_raw.upper(),
            defaults={
                "description": uom_raw,
                "international_stnd_code": uom_raw.upper(),
            },
        )
        if unit_created:
            stats["units_created"] += 1

    # Category
    category = None
    if category_raw:
        category = ItemCategory.objects.filter(code__iexact=category_raw).first()
        if not category:
            category, cat_created = ItemCategory.objects.get_or_create(
                code=category_raw.upper()[:10],
                defaults={"description": category_raw},
            )
            if cat_created:
                stats["categories_created"] += 1

    # Posting groups (only when coming from config-package template)
    gen_prod_posting = None
    if gen_posting_raw:
        gen_prod_posting, _ = GeneralProductPostingGroup.objects.get_or_create(
            code=gen_posting_raw.upper(),
            defaults={"description": gen_posting_raw},
        )

    inv_posting = None
    if inv_posting_raw:
        inv_posting, _ = InventoryPostingGroup.objects.get_or_create(
            code=inv_posting_raw.upper(),
            defaults={"description": inv_posting_raw},
        )

    # Build item data
    item_data = {
        "item_name": item_name,
        "unit_of_measure": unit,
        "item_category": category,
        "unit_price": int(float(unit_price_raw)) if unit_price_raw else 0,
        "type": type_raw if type_raw else "Inventory",
        "description": description_raw,
        "shelf_no": shelf_no_raw,
    }
    if unit_cost_item_raw is not None and str(unit_cost_item_raw).strip() != "":
        try:
            from items.models import money_decimal

            item_data["manual_unit_cost"] = money_decimal(unit_cost_item_raw)
        except (TypeError, ValueError):
            pass
    if bar_code_raw:
        item_data["bar_code_no"] = bar_code_raw
    if gen_prod_posting:
        item_data["general_product_posting_group"] = gen_prod_posting
    if inv_posting:
        item_data["inventory_posting_group"] = inv_posting
    if costing_raw:
        item_data["costing_method"] = costing_raw
    if blocked_raw and not pd.isna(blocked_raw):
        item_data["blocked"] = bool(blocked_raw)

    item = Item.objects.filter(item_name=item_name).first()
    if item:
        for key, value in item_data.items():
            if key != "no":
                setattr(item, key, value)
        item.save()
        stats["items_updated"] += 1
    else:
        item = Item.objects.create(**item_data)
        stats["items_created"] += 1

    return item


def _update_task_status(task, processed, updated, total, message):
    """Update the task status with progress information"""
    progress = (processed / total * 100) if total > 0 else 0
    task.update_state(
        state="PROGRESS",
        meta={
            "progress": round(progress, 2),
            "processed": processed,
            "updated": updated,
            "total": total,
            "message": message,
        },
    )


def _update_task_error(task, index, total_rows, error_message):
    """Update task status with error"""
    progress = int((index / total_rows) * 100) if total_rows > 0 else 0
    task.update_state(
        state="PROGRESS",
        meta={
            "progress": progress,
            "current": index,
            "total": total_rows,
            "message": f"Error on row {index + 4}: {error_message}",
            "error_details": error_message,
            "status": "error",
        },
    )


@shared_task(bind=True)
def process_journal_import(
    self,
    df_json=None,
    schema_name=None,
    user_id=None,
    file_path=None,
    branch_id=None,
    create_missing_items=False,
    default_tracking_code="ALL LOT",
    auto_pick_lot_for_negative=True,
    auto_pick_lot_for_positive=True,
    lot_pick_strategy="fifo",
    auto_fill_unit_amount=True,
    create_missing_lot_expiry_for_missing=False,
    missing_lot_expiry_date=None,
    default_adjustment_type="operational",
):
    """
    Process journal import from DataFrame JSON or an Excel file path.
    Supports both the legacy config-package flow (df_json) and the
    simple-import flow (file_path) with user-friendly column names.
    """
    logger = get_task_logger(__name__)

    # Maps user-friendly names from the simple template to legacy column names
    COLUMN_ALIASES = {
        "Adjustment Type": "Entry Type",
        "Entry Type": "Entry Type",
        "Unit of Measure": "Unit Of Measure",
        "Location": "Location Code",
        "Item Name": "Item",
        "Lot No": "Lot No",
        "Lot No.": "Lot No",
        "Batch": "Lot No",
        "Batch / Lot": "Lot No",
        "Batch/Lot": "Lot No",
        "Expiry Date": "Expiry Date",
        "Expiration Date": "Expiry Date",
    }
    ENTRY_TYPE_MAP = {
        "increase inventory": "PositiveAdjustment",
        "decrease inventory": "NegativeAdjustment",
        "positive adjustment": "PositiveAdjustment",
        "negative adjustment": "NegativeAdjustment",
    }
    ADJUSTMENT_CATEGORY_MAP = {
        "operational": "operational",
        "operational adjustment": "operational",
        "opening_balance": "opening_balance",
        "opening balance": "opening_balance",
    }
    default_adj_type = (
        default_adjustment_type
        if default_adjustment_type in ("operational", "opening_balance")
        else "operational"
    )

    try:
        if not schema_name:
            schema_name = settings.PUBLIC_SCHEMA_NAME

        with schema_context(schema_name):
            if file_path:
                df = pd.read_excel(file_path, header=0)
                df.columns = df.columns.str.strip()
                # Normalise simple-template column names
                df.rename(columns=COLUMN_ALIASES, inplace=True)
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            elif df_json:
                df = pd.read_json(df_json, orient="records")
            else:
                return {
                    "success": False,
                    "message": "No data provided",
                    "meta": {"progress": 0, "status": "failed", "journals_created": 0, "journals_updated": 0},
                    "state": "FAILURE",
                }

            df = df.fillna("")
            total_rows = len(df)

            user = None
            try:
                if user_id:
                    user = User.objects.get(id=user_id)
                if not user:
                    user = User.objects.filter(is_superuser=True).first()
                if not user:
                    raise ValidationError("No valid user found for journal import")
            except User.DoesNotExist:
                user = User.objects.filter(is_superuser=True).first()
                if not user:
                    raise ValidationError("No valid user found for journal import")

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 0,
                    "current": 0,
                    "total": total_rows,
                    "message": f"Starting import of {total_rows} journal entries...",
                    "status": "processing",
                    "journals_created": 0,
                    "journals_updated": 0,
                },
            )

            journals_created = 0
            journals_updated = 0
            row_errors = []

            from items.models import ItemUnitOfMeasure as ItemUOM
            from items.models import ItemJournalTemplate, ItemJournalBatch
            from items.models import ItemTrackingCodes
            from dimension.models import get_posting_dimension_payload
            from dimension.models import DimensionValue

            # Ensure the default ITEM journal template/batch exists for inventory adjustments.
            # Relying on ItemJournal.save() keeps legacy flows working, but simple-import creates
            # records directly and we want stable defaults.
            default_template, _ = ItemJournalTemplate.objects.get_or_create(
                name="ITEM",
                defaults={"description": "Item Journal", "type": "item"},
            )
            default_batch, _ = ItemJournalBatch.objects.get_or_create(
                journal_template=default_template,
                name="DEFAULT",
                defaults={"description": "Default Journal"},
            )
            # Wire number series from Inventory Setup when the ITEM template has none yet
            # (so ItemJournal.save() can assign document_no from NoSeriesLines).
            try:
                from setup.models import InventorySetup

                inv_setup = InventorySetup.objects.all().first()
                series = getattr(inv_setup, "item_journal_no_series", None) if inv_setup else None
                if series:
                    tpl_updates = []
                    if not default_template.no_series_id:
                        default_template.no_series = series
                        tpl_updates.append("no_series")
                    if tpl_updates:
                        default_template.save(update_fields=tpl_updates)
                    batch_updates = []
                    if not default_batch.no_series_id:
                        default_batch.no_series = series
                        batch_updates.append("no_series")
                    if batch_updates:
                        default_batch.save(update_fields=batch_updates)
            except Exception:
                pass

            # Resolve posting dimensions for this import.
            # Prefer explicit branch_id (captured from X-Branch-Id in the API request),
            # fallback to the initiating user's assigned branch.
            branch_value = None
            if branch_id:
                try:
                    branch_value = DimensionValue.objects.filter(pk=int(branch_id)).first()
                except Exception:
                    branch_value = None
            if not branch_value:
                branch_value = getattr(user, "global_dimension_1", None)

            # get_posting_dimension_payload also safely fills mandatory global dimensions.
            dim_payload = get_posting_dimension_payload(global_dimension_1=branch_value)

            with transaction.atomic():
                configured_missing_expiry = None
                if missing_lot_expiry_date:
                    try:
                        configured_missing_expiry = pd.to_datetime(
                            missing_lot_expiry_date
                        ).date()
                    except Exception:
                        configured_missing_expiry = None

                for index, row in df.iterrows():
                    try:
                        row_status = str(row.get("Status", "")).strip().lower()
                        if row_status == "posted":
                            continue

                        item_name = str(row.get("Item", "")).strip()
                        item_no = str(row.get("Item No", "")).strip()
                        if not item_name and not item_no:
                            continue

                        item = None
                        if item_name:
                            item = (
                                Item.objects.filter(item_name__iexact=item_name).first()
                                or Item.objects.filter(no=item_name).first()
                            )
                        if not item and item_no:
                            item = Item.objects.filter(no=item_no).first()
                        if not item:
                            if not create_missing_items:
                                row_errors.append(
                                    f"Row {index + 2}: Item '{item_name or item_no}' not found"
                                )
                                continue

                            # Create missing item (Inventory) with defaults and optional tracking/UOM.
                            raw_uom_for_item = str(row.get("Unit Of Measure", "")).strip()
                            uom_obj = None
                            if raw_uom_for_item:
                                uom_code = raw_uom_for_item.upper()
                                uom_obj, _ = UnitOfMeasure.objects.get_or_create(
                                    code=uom_code,
                                    defaults={
                                        "description": raw_uom_for_item,
                                        "international_stnd_code": uom_code,
                                    },
                                )

                            # Set tracking code when lot/expiry present in this row.
                            raw_lot_for_item = str(
                                row.get("Lot No", row.get("Lot No.", ""))
                            ).strip()
                            raw_exp_for_item = row.get("Expiry Date", "")
                            has_exp_for_item = (
                                raw_exp_for_item is not None and str(raw_exp_for_item).strip()
                            )

                            tracking_obj = None
                            if raw_lot_for_item or has_exp_for_item:
                                tracking_obj, _ = ItemTrackingCodes.objects.get_or_create(
                                    code=default_tracking_code,
                                    defaults={
                                        "description": default_tracking_code,
                                        "require_serial_no": False,
                                        "require_lot_no": True,
                                        "require_expiry_date": bool(has_exp_for_item),
                                    },
                                )

                            item = Item(
                                item_name=item_name,
                                type="Inventory",
                            )
                            if uom_obj:
                                item.unit_of_measure = uom_obj
                            if tracking_obj:
                                item.tracking_code = tracking_obj
                            item.save()

                            # Ensure posting groups exist (Item.save() assigns defaults when configured).
                            if not item.general_product_posting_group:
                                raise ValidationError(
                                    "Missing General Product Posting Group default. "
                                    "Please mark a General Product Posting Group as default before importing."
                                )
                            if not item.inventory_posting_group:
                                raise ValidationError(
                                    "Missing Inventory Posting Group default. "
                                    "Please mark an Inventory Posting Group as default before importing."
                                )

                        raw_entry_type = str(row.get("Entry Type", "")).strip()
                        entry_type = ENTRY_TYPE_MAP.get(
                            raw_entry_type.lower(), raw_entry_type
                        )

                        raw_adj_category = str(
                            row.get("Adjustment Category", row.get("adjustment_type", ""))
                        ).strip()
                        adjustment_type = ADJUSTMENT_CATEGORY_MAP.get(
                            raw_adj_category.lower(), ""
                        ) or default_adj_type

                        raw_qty = row.get("Quantity", 0)
                        quantity = int(float(raw_qty)) if raw_qty else 0
                        if quantity <= 0:
                            row_errors.append(f"Row {index + 2}: Quantity must be greater than zero")
                            continue

                        raw_uom = str(row.get("Unit Of Measure", "")).strip()
                        item_uom = None
                        if raw_uom:
                            uom_obj = UnitOfMeasure.objects.filter(code__iexact=raw_uom).first()
                            if uom_obj:
                                item_uom, _ = ItemUOM.objects.get_or_create(
                                    item=item,
                                    unit_of_measure=uom_obj,
                                    defaults={"quantity_per_unit": 1},
                                )
                        if not item_uom:
                            item_uom = (
                                ItemUOM.objects.filter(item=item, default=True).first()
                                or ItemUOM.objects.filter(item=item).order_by("id").first()
                            )

                        raw_loc = str(row.get("Location Code", "")).strip()
                        location = None
                        if raw_loc:
                            from items.models import Location as Loc
                            location = (
                                Loc.objects.filter(description__iexact=raw_loc).first()
                                or Loc.objects.filter(code__iexact=raw_loc).first()
                            )
                            if not location:
                                raise ValidationError(
                                    f"Unknown Location '{raw_loc}'. "
                                    "Use the Location Code exactly as configured in the system."
                                )
                        else:
                            # If no explicit Location was provided, derive it from the branch convention:
                            # Location.code == DimensionValue.code (e.g. MWANJARI).
                            if dim_payload.get("global_dimension_1") is not None:
                                from items.models import Location as Loc

                                location = Loc.objects.filter(
                                    code__iexact=getattr(dim_payload.get("global_dimension_1"), "code", "")
                                ).first()
                                if not location:
                                    raise ValidationError(
                                        f"No Location found for branch {getattr(dim_payload.get('global_dimension_1'), 'code', None)!r}. "
                                        "Add a Location whose code matches the branch code, or fill the Location column."
                                    )

                        raw_date = row.get("Date", "")
                        if raw_date and str(raw_date).strip():
                            try:
                                posting_date = pd.to_datetime(raw_date).date()
                            except Exception:
                                posting_date = datetime.now().date()
                        else:
                            posting_date = datetime.now().date()

                        desc = str(row.get("Description", "")).strip()

                        qty_per_uom = (
                            int(getattr(item_uom, "quantity_per_unit", 1) or 1)
                            if item_uom
                            else 1
                        )
                        required_base_qty = int(quantity) * qty_per_uom

                        # Optional tracking (lot / expiry) from template columns
                        raw_lot = str(
                            row.get("Lot No", row.get("Lot No.", ""))
                        ).strip()
                        raw_exp = row.get("Expiry Date", "")
                        exp_date = None
                        if raw_exp is not None and str(raw_exp).strip():
                            try:
                                exp_date = pd.to_datetime(raw_exp).date()
                            except Exception:
                                raise ValidationError(
                                    f"Invalid Expiry Date: {raw_exp!r} (use YYYY-MM-DD)"
                                )

                        tracking = item.tracking_code
                        reqs = item.requires_tracking_line if tracking else {}
                        requires_lot_tracking = bool(
                            tracking and isinstance(reqs, dict) and reqs.get("lot_no")
                        )
                        is_negative_adjustment = str(entry_type).lower() in (
                            "negativeadjustment",
                            "negative adjustment",
                        )
                        is_positive_adjustment = str(entry_type).lower() in (
                            "positiveadjustment",
                            "positive adjustment",
                        )

                        selected_lot_entry = None
                        if (
                            requires_lot_tracking
                            and (is_negative_adjustment or is_positive_adjustment)
                        ):
                            lot_qs = ItemLedgerEntries.objects.filter(
                                item=item,
                            )
                            if location:
                                lot_qs = lot_qs.filter(location=location)
                            if dim_payload.get("global_dimension_1") is not None:
                                lot_qs = lot_qs.filter(
                                    global_dimension_1=dim_payload.get("global_dimension_1")
                                )
                            lot_qs = lot_qs.exclude(lot_no__isnull=True).exclude(lot_no="")
                            lot_qs_positive = lot_qs
                            if is_negative_adjustment:
                                lot_qs = lot_qs.filter(remaining_quantity__gt=0)

                            lot_rows = list(
                                (lot_qs if is_negative_adjustment else lot_qs_positive).values(
                                    "lot_no",
                                    "expiry_date",
                                    "created_at",
                                    "remaining_quantity",
                                ).order_by("created_at", "id")
                            )
                            lot_candidates_map = {}
                            for row_lot in lot_rows:
                                lot_key = row_lot.get("lot_no")
                                if not lot_key:
                                    continue
                                if lot_key not in lot_candidates_map:
                                    lot_candidates_map[lot_key] = {
                                        "lot_no": lot_key,
                                        "expiry_date": row_lot.get("expiry_date"),
                                        "available_qty": 0,
                                        "first_seen": row_lot.get("created_at"),
                                    }
                                lot_candidates_map[lot_key]["available_qty"] += int(
                                    row_lot.get("remaining_quantity") or 0
                                )
                                if (
                                    row_lot.get("expiry_date")
                                    and not lot_candidates_map[lot_key].get("expiry_date")
                                ):
                                    lot_candidates_map[lot_key]["expiry_date"] = row_lot.get(
                                        "expiry_date"
                                    )
                            lot_candidates = sorted(
                                lot_candidates_map.values(),
                                key=lambda c: c.get("first_seen"),
                            )
                            if lot_pick_strategy != "fifo":
                                # Current request uses FIFO. Keep deterministic FIFO fallback.
                                lot_candidates = sorted(
                                    lot_candidates,
                                    key=lambda c: c.get("first_seen"),
                                )

                            preferred_lot = raw_lot if raw_lot else None
                            candidate = None
                            if is_negative_adjustment:
                                candidate = _pick_fifo_lot_candidate(
                                    lot_candidates,
                                    required_base_qty,
                                    preferred_lot_no=preferred_lot,
                                )
                                preferred_exists = any(
                                    (c.get("lot_no") or "").strip().lower()
                                    == (preferred_lot or "").strip().lower()
                                    for c in lot_candidates
                                )
                                if preferred_lot and candidate is None:
                                    if (
                                        create_missing_lot_expiry_for_missing
                                        and not preferred_exists
                                    ):
                                        # Keep provided lot; create expiry when missing.
                                        if exp_date is None:
                                            exp_date = (
                                                configured_missing_expiry or posting_date
                                            )
                                    else:
                                        row_errors.append(
                                            f"Row {index + 2}: Lot '{preferred_lot}' has insufficient available quantity "
                                            f"for item '{item.item_name}' (required base qty: {required_base_qty})."
                                        )
                                        continue
                                if not preferred_lot and auto_pick_lot_for_negative:
                                    if candidate is None:
                                        if create_missing_lot_expiry_for_missing:
                                            raw_lot = _build_import_lot_no(
                                                item.no, index + 2
                                            )
                                            if exp_date is None:
                                                exp_date = (
                                                    configured_missing_expiry
                                                    or posting_date
                                                )
                                        else:
                                            row_errors.append(
                                                f"Row {index + 2}: No available lot found for item '{item.item_name}' "
                                                f"(required base qty: {required_base_qty})."
                                            )
                                            continue
                                    else:
                                        raw_lot = candidate.get("lot_no") or raw_lot
                                        if exp_date is None:
                                            exp_date = candidate.get("expiry_date")
                            elif is_positive_adjustment:
                                if preferred_lot:
                                    candidate = next(
                                        (
                                            c
                                            for c in lot_candidates
                                            if (c.get("lot_no") or "").strip().lower()
                                            == preferred_lot.strip().lower()
                                        ),
                                        None,
                                    )
                                    if candidate is None:
                                        if create_missing_lot_expiry_for_missing:
                                            if exp_date is None:
                                                exp_date = (
                                                    configured_missing_expiry
                                                    or posting_date
                                                )
                                        else:
                                            row_errors.append(
                                                f"Row {index + 2}: Lot '{preferred_lot}' does not exist for item '{item.item_name}'."
                                            )
                                            continue
                                elif auto_pick_lot_for_positive:
                                    candidate = lot_candidates[0] if lot_candidates else None
                                    if candidate is None:
                                        if create_missing_lot_expiry_for_missing:
                                            raw_lot = _build_import_lot_no(
                                                item.no, index + 2
                                            )
                                            if exp_date is None:
                                                exp_date = (
                                                    configured_missing_expiry
                                                    or posting_date
                                                )
                                        else:
                                            row_errors.append(
                                                f"Row {index + 2}: No existing lot found for item '{item.item_name}'."
                                            )
                                            continue
                                    else:
                                        raw_lot = candidate.get("lot_no") or raw_lot
                                if candidate and exp_date is None:
                                    exp_date = candidate.get("expiry_date")

                            if raw_lot:
                                selected_lot_entry = (
                                    (lot_qs_positive if is_positive_adjustment else lot_qs).filter(
                                        lot_no=raw_lot
                                    )
                                    .order_by("created_at", "id")
                                    .first()
                                )

                        journal_data = {
                            "item": item,
                            "entry_type": entry_type,
                            "description": desc,
                            "quantity": quantity,
                            "date": posting_date,
                            "user": user,
                            "adjustment_type": adjustment_type,
                            "journal_template": default_template,
                            "journal_batch": default_batch,
                            "global_dimension_1": dim_payload.get("global_dimension_1"),
                            "global_dimension_2": dim_payload.get("global_dimension_2"),
                            "dimension_set": dim_payload.get("dimension_set"),
                        }
                        if item_uom:
                            journal_data["item_unit_of_measure"] = item_uom
                        if location:
                            journal_data["location_code"] = location

                        # Legacy columns (config-package template)
                        doc_no = str(row.get("Document No", "")).strip()
                        # When Document No is omitted, leave it unset so ItemJournal.save()
                        # assigns the next number from the journal template's no_series (same as UI).
                        if doc_no:
                            journal_data["document_no"] = doc_no
                        from items.models import money_decimal

                        raw_cost = row.get("Unit Cost", "")
                        if raw_cost and str(raw_cost).strip():
                            journal_data["unit_cost"] = money_decimal(raw_cost)
                        raw_amount = row.get("Unit Amount", "")
                        if auto_fill_unit_amount:
                            resolved_unit_amount = _resolve_unit_amount_for_import(
                                raw_unit_amount=raw_amount,
                                raw_unit_cost=raw_cost,
                                lot_entry=selected_lot_entry,
                                item=item,
                            )
                            if resolved_unit_amount is None:
                                row_errors.append(
                                    f"Row {index + 2}: Unable to resolve Unit Amount for item '{item.item_name}'."
                                )
                                continue
                            journal_data["unit_amount"] = resolved_unit_amount
                            journal_data["unit_cost"] = resolved_unit_amount
                        elif raw_amount and str(raw_amount).strip():
                            journal_data["unit_amount"] = money_decimal(raw_amount)
                            if not journal_data.get("unit_cost"):
                                journal_data["unit_cost"] = money_decimal(raw_amount)
                        elif raw_cost and str(raw_cost).strip():
                            journal_data["unit_amount"] = money_decimal(raw_cost)
                            journal_data["unit_cost"] = money_decimal(raw_cost)

                        if index % 5 == 0:
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "progress": int((index / total_rows) * 100),
                                    "current": index,
                                    "total": total_rows,
                                    "message": f"Processing journals... ({index}/{total_rows})",
                                    "journals_created": journals_created,
                                    "journals_updated": journals_updated,
                                    "status": "processing",
                                },
                            )

                        journal = None
                        if doc_no:
                            journal = ItemJournal.objects.filter(document_no=doc_no).first()

                        if journal:
                            if journal.status == "Posted":
                                row_errors.append(
                                    f"Row {index + 2}: Journal '{doc_no}' is already posted and cannot be updated."
                                )
                                continue
                            for key, value in journal_data.items():
                                setattr(journal, key, value)
                            journal.save()
                            journals_updated += 1
                        else:
                            journal = ItemJournal.objects.create(**journal_data)
                            journals_created += 1

                        if tracking and reqs.get("lot_no") and not raw_lot:
                            raise ValidationError(
                                "Lot No is required for this item (tracking code requires lot)."
                            )
                        if tracking and reqs.get("expiry_date") and exp_date is None:
                            raise ValidationError(
                                "Expiry Date is required for this item (tracking code requires expiry)."
                            )

                        if raw_lot or exp_date is not None:
                            if not tracking:
                                raise ValidationError(
                                    "Lot/Expiry provided but item has no Tracking Code configured."
                                )
                            if not location:
                                raise ValidationError(
                                    "Location is required when importing Lot/Expiry tracking lines."
                                )

                            spec = TrackingSpecification.objects.filter(
                                item_journal=journal,
                                lot_no=raw_lot or None,
                                expiry_date=exp_date,
                            ).first()
                            if not spec:
                                spec_desc = (
                                    desc
                                    or f"Adjustment import — {journal.document_no or journal.id}"
                                )[:255]
                                spec = TrackingSpecification(
                                    item=item,
                                    location_code=location,
                                    serial_no=None,
                                    lot_no=raw_lot or None,
                                    expiry_date=exp_date,
                                    quantity_base=required_base_qty,
                                    item_journal=journal,
                                    source_template=journal.journal_template,
                                    source_batch=journal.journal_batch,
                                    description=spec_desc,
                                    user=user,
                                )
                                spec.save()
                            else:
                                spec.quantity_base = required_base_qty
                                spec.location_code = location
                                spec_desc = (
                                    desc
                                    or spec.description
                                    or f"Adjustment import — {journal.document_no or journal.id}"
                                )[:255]
                                spec.description = spec_desc
                                spec.user = user
                                spec.save()

                            if journal.item_specification_id != spec.id:
                                journal.item_specification = spec
                                journal.save(update_fields=["item_specification"])

                    except Exception as e:
                        row_errors.append(f"Row {index + 2}: {str(e)}")
                        logger.error(f"Error on row {index + 2}: {str(e)}", exc_info=True)
                        continue

            errors_download_key = None
            if row_errors:
                try:
                    task_id_str = str(self.request.id)
                    errors_download_key = f"adj_import_errors_{schema_name}_{task_id_str}"
                    # Store for 2 hours.
                    cache.set(errors_download_key, row_errors, timeout=7200)
                except Exception:
                    errors_download_key = None

            return {
                "success": True,
                "message": "Import completed successfully",
                "meta": {
                    "progress": 100,
                    "current": total_rows,
                    "total": total_rows,
                    "message": "Import completed successfully",
                    "journals_created": journals_created,
                    "journals_updated": journals_updated,
                    "failed_count": len(row_errors),
                    # Keep payload small; store full list in cache for download.
                    "errors": row_errors[:100],
                    "errors_download_key": errors_download_key,
                    "status": "completed",
                },
                "state": "SUCCESS",
            }

    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Import failed: {str(e)}",
            "meta": {
                "progress": 0,
                "message": f"Import failed: {str(e)}",
                "status": "failed",
                "error": str(e),
                "journals_created": 0,
                "journals_updated": 0,
            },
            "state": "FAILURE",
        }


def _resolve_export_branch(branch_id):
    """Resolve branch DimensionValue for item export when multi-branch is enabled."""
    try:
        from financials.models import GeneralLedgerSetup
        from dimension.models import DimensionValue

        gl_setup = GeneralLedgerSetup.objects.first()
        if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
            return None
        if not branch_id:
            return None
        return DimensionValue.objects.filter(pk=int(branch_id)).first()
    except Exception:
        return None


def _prepare_items_export_queryset(queryset, filters_data=None, branch=None):
    """
    Apply list-like filters and annotate branch-scoped inventory/cost for export.
    Mirrors ItemsModalViewSet.get_queryset list behaviour for inventory/cost.
    """
    from decimal import Decimal
    from django.db.models import (
        Case,
        DecimalField,
        F,
        IntegerField,
        OuterRef,
        Q,
        Subquery,
        Sum,
        Value,
        When,
    )
    from django.db.models.functions import Coalesce

    filters_data = filters_data or {}

    # Match list default: hide blocked unless explicitly requested
    include_blocked = str(filters_data.get("include_blocked", "")).lower() in (
        "1",
        "true",
        "yes",
    )
    if filters_data.get("blocked") is None and not include_blocked:
        queryset = queryset.filter(blocked=False)
    elif filters_data.get("blocked") is not None:
        blocked_val = str(filters_data.get("blocked")).lower() in ("1", "true", "yes")
        queryset = queryset.filter(blocked=blocked_val)

    search = (filters_data.get("search") or filters_data.get("q") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(item_name__icontains=search)
            | Q(bar_code_no__icontains=search)
            | Q(no__icontains=search)
            | Q(description__icontains=search)
            | Q(shelf_no__icontains=search)
        )
    if filters_data.get("item_name"):
        queryset = queryset.filter(item_name__icontains=filters_data["item_name"])
    if filters_data.get("item_category"):
        queryset = queryset.filter(item_category__code=filters_data["item_category"])
    if filters_data.get("type"):
        queryset = queryset.filter(type=filters_data["type"])

    # Branch-scoped inventory (same expression as list page)
    if branch:
        inventory_expr = Coalesce(
            Sum(
                Case(
                    When(
                        itemledgerentries__global_dimension_1_id=branch.id,
                        then=F("itemledgerentries__remaining_quantity"),
                    ),
                    default=Value(0),
                )
            ),
            0,
            output_field=IntegerField(),
        )
        ve_qs = ValueEntry.objects.filter(
            item=OuterRef("pk"),
            global_dimension_1_id=branch.id,
        ).order_by("-created_at")
    else:
        inventory_expr = Coalesce(
            Sum("itemledgerentries__remaining_quantity"),
            0,
            output_field=IntegerField(),
        )
        ve_qs = ValueEntry.objects.filter(item=OuterRef("pk")).order_by("-created_at")

    cost_from_ve = Coalesce(
        Subquery(
            ve_qs.values("cost_per_unit")[:1],
            output_field=DecimalField(max_digits=15, decimal_places=2),
        ),
        Value(Decimal("0.00")),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )

    queryset = queryset.select_related("item_category", "unit_of_measure").annotate(
        _export_inventory=inventory_expr,
        _export_unit_cost=Case(
            When(
                type__in=["Service", "Non-Inventory"],
                then=Coalesce(
                    F("manual_unit_cost"),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            ),
            default=cost_from_ve,
            output_field=DecimalField(max_digits=15, decimal_places=2),
        ),
    )

    # Optional inventory filters (branch-aware via annotation above)
    inventory_status = filters_data.get("inventory_status")
    low_stock_param = filters_data.get("low_stock")
    low_stock = str(low_stock_param).lower() in ("true", "1")
    inventory_min = filters_data.get("inventory_min")
    inventory_max = filters_data.get("inventory_max")

    if inventory_status == "IN_STOCK":
        queryset = queryset.filter(_export_inventory__gt=0)
    elif inventory_status == "OUT_OF_STOCK":
        queryset = queryset.filter(_export_inventory__lte=0)
    if low_stock:
        queryset = queryset.filter(
            type=InventoryType.Inventory.value,
            minimum_stock__isnull=False,
            minimum_stock__gt=0,
            _export_inventory__gt=0,
            _export_inventory__lte=F("minimum_stock"),
        )
    if inventory_min is not None and inventory_min != "":
        try:
            queryset = queryset.filter(_export_inventory__gte=int(inventory_min))
        except (ValueError, TypeError):
            pass
    if inventory_max is not None and inventory_max != "":
        try:
            queryset = queryset.filter(_export_inventory__lte=int(inventory_max))
        except (ValueError, TypeError):
            pass

    return queryset.order_by("item_name")


def _export_item_inventory(item):
    annotated = getattr(item, "_export_inventory", None)
    if annotated is not None:
        return float(annotated or 0)
    return float(item.inventory) if item.inventory else 0


def _export_item_unit_cost(item):
    annotated = getattr(item, "_export_unit_cost", None)
    if annotated is not None:
        return float(annotated or 0)
    return float(item.unit_cost) if item.unit_cost else 0


def _export_item_profit_pct(item):
    """Profit % from unit price and export (branch-aware) unit cost."""
    from decimal import Decimal

    unit_price = Decimal(str(item.unit_price or 0))
    if unit_price <= 0:
        return 0
    unit_cost = Decimal(str(_export_item_unit_cost(item)))
    return float(round(((unit_price - unit_cost) / unit_price) * 100, 0))


@shared_task(bind=True)
def export_items_task(
    self,
    item_ids,
    export_format,
    filters_data=None,
    schema_name=None,
    user_permissions=None,
    branch_id=None,
):
    """
    Background task to export items to Excel or PDF format
    Args:
        self: Task instance
        item_ids: List of item IDs to export (or None for all)
        export_format: 'excel' or 'pdf'
        filters_data: Optional filter dictionary
        schema_name: Schema name for tenant
        user_permissions: Dict with user permission flags
        branch_id: Optional DimensionValue id for branch-scoped inventory/cost
    """
    logger = get_task_logger(__name__)

    try:
        from django_tenants.utils import schema_context
        from django.db import connection

        schema_name = schema_name or connection.schema_name

        with schema_context(schema_name):
            # Update initial status
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 10,
                    "message": "Preparing export...",
                    "status": "processing",
                },
            )

            # Get queryset
            if item_ids:
                queryset = Item.objects.filter(id__in=item_ids)
            else:
                queryset = Item.objects.all()

            branch = _resolve_export_branch(branch_id)
            queryset = _prepare_items_export_queryset(
                queryset, filters_data=filters_data, branch=branch
            )

            # Evaluate queryset and limit to 10000 items
            items = list(queryset[:10000])
            total_items = len(items)

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 30,
                    "message": f"Exporting {total_items} items...",
                    "status": "processing",
                },
            )

            # Generate export file
            if export_format == "excel":
                file_data, filename = _export_to_excel(
                    items, user_permissions=user_permissions
                )
            elif export_format == "pdf":
                file_data, filename = _export_to_pdf(
                    items, user_permissions=user_permissions
                )
            else:
                raise ValueError(f"Invalid format: {export_format}")

            # Encode file data to base64 for storage in cache
            logger.info(f"Encoding {len(file_data)} bytes to base64")
            file_data_base64 = base64.b64encode(file_data).decode("utf-8")
            logger.info(f"Base64 encoded length: {len(file_data_base64)} characters")

            # Store in cache with task_id and schema_name as key (expires in 2 hours)
            # Use string conversion to ensure consistency and include schema for tenant isolation
            task_id_str = str(self.request.id)
            cache_key = f"export_file_{schema_name}_{task_id_str}"

            file_info = {
                "file_data": file_data_base64,
                "filename": filename,
                "content_type": (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if export_format == "excel"
                    else "application/pdf"
                ),
            }

            # Store in cache with longer timeout (2 hours) to account for slow downloads
            cache.set(cache_key, file_info, timeout=7200)

            # Verify cache was set and data integrity
            cached_value = cache.get(cache_key)
            if cached_value:
                # Verify the cached data can be decoded back
                try:
                    test_decode = base64.b64decode(cached_value["file_data"])
                    if (
                        len(test_decode) == len(file_data)
                        and test_decode[:10] == file_data[:10]
                    ):
                        logger.info(
                            f"Export file stored in cache successfully. Key: {cache_key}, size: {len(file_data)} bytes, verified integrity"
                        )
                    else:
                        logger.error(
                            f"Cache integrity check failed! Original: {len(file_data)} bytes, Decoded: {len(test_decode)} bytes"
                        )
                except Exception as e:
                    logger.error(f"Failed to verify cached data: {str(e)}")
            else:
                logger.error(f"Failed to store export file in cache. Key: {cache_key}")

            return {
                "success": True,
                "message": f"Export completed successfully",
                "status": "completed",
                "progress": 100,
                "filename": filename,
                "task_id": task_id_str,
                "cache_key": cache_key,  # Include in result for retrieval
                "schema_name": schema_name,  # Include schema for verification
            }

    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Export failed: {str(e)}",
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }


def _export_to_excel(items, user_permissions=None):
    """Export items to Excel format with user permission filtering - returns (file_data, filename)"""
    import xlsxwriter
    import logging

    logger = logging.getLogger(__name__)

    # Get user permissions
    can_see_buying_price = True
    can_see_profit = True

    if user_permissions:
        can_see_buying_price = user_permissions.get("can_see_buying_price", True)
        can_see_profit = user_permissions.get("can_see_profit_margin", True)

    # Create BytesIO buffer for the Excel file
    output = BytesIO()

    # Create workbook - don't use in_memory option with BytesIO
    workbook = xlsxwriter.Workbook(output, {"strings_to_urls": False})
    worksheet = workbook.add_worksheet("Items")

    logger.info(
        f"Starting Excel export for {len(items)} items (permissions: buying_price={can_see_buying_price}, profit={can_see_profit})"
    )

    # Define formats
    header_format = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#366092",
            "font_color": "white",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    data_format = workbook.add_format({"border": 1})
    number_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})

    # Define headers based on permissions
    headers = [
        "Item No",
        "Item Name",
        "Description",
        "Category",
        "Type",
        "Unit of Measure",
        "Unit Price",
    ]

    # Add Unit Cost column only if user has permission
    if can_see_buying_price:
        headers.append("Unit Cost")

    # Add Profit Margin column only if user has permission
    if can_see_profit:
        headers.append("Profit Margin %")

    headers.extend(
        [
            "Inventory",
            "Bar Code",
            "Shelf No",
            "Status",
        ]
    )

    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
        worksheet.set_column(col, col, 15)

    # Write data
    for row_idx, item in enumerate(items, start=1):
        col = 0
        worksheet.write(row_idx, col, item.no or "", data_format)
        col += 1
        worksheet.write(row_idx, col, item.item_name or "", data_format)
        col += 1
        worksheet.write(row_idx, col, item.description or "", data_format)
        col += 1
        worksheet.write(
            row_idx,
            col,
            item.item_category.description if item.item_category else "",
            data_format,
        )
        col += 1
        worksheet.write(row_idx, col, item.type or "", data_format)
        col += 1
        # Convert unit_of_measure ForeignKey to string (code)
        unit_of_measure_str = item.unit_of_measure.code if item.unit_of_measure else ""
        worksheet.write(row_idx, col, unit_of_measure_str, data_format)
        col += 1
        worksheet.write(
            row_idx,
            col,
            float(item.unit_price) if item.unit_price else 0,
            number_format,
        )
        col += 1

        # Write Unit Cost only if user has permission (branch-scoped when annotated)
        if can_see_buying_price:
            worksheet.write(
                row_idx,
                col,
                _export_item_unit_cost(item),
                number_format,
            )
            col += 1

        # Write Profit Margin only if user has permission (branch-scoped when annotated)
        if can_see_profit:
            worksheet.write(row_idx, col, _export_item_profit_pct(item), number_format)
            col += 1

        worksheet.write(
            row_idx, col, _export_item_inventory(item), number_format
        )
        col += 1
        worksheet.write(row_idx, col, item.bar_code_no or "", data_format)
        col += 1
        worksheet.write(row_idx, col, item.shelf_no or "", data_format)
        col += 1
        worksheet.write(
            row_idx, col, "Active" if not item.blocked else "Blocked", data_format
        )
        col += 1

    # Close workbook to finalize the file - this writes all data to BytesIO
    workbook.close()

    logger.info("Workbook closed, retrieving file data from BytesIO")

    # Get the file data - use getvalue() to get all bytes from BytesIO
    file_data = output.getvalue()

    logger.info(f"File data retrieved: {len(file_data)} bytes")
    logger.info(
        f"First 10 bytes (hex): {file_data[:10].hex() if len(file_data) >= 10 else file_data.hex()}"
    )

    output.close()

    # Verify file data is not empty
    if not file_data or len(file_data) == 0:
        raise ValueError("Generated Excel file is empty")

    # Verify the file has the correct Excel signature (PK for ZIP format)
    if len(file_data) < 4 or file_data[:2] != b"PK":
        raise ValueError(
            f"Invalid Excel file signature. First bytes: {file_data[:10].hex() if len(file_data) >= 10 else file_data.hex()}"
        )

    logger.info("Excel file generated successfully with valid signature")

    filename = f"items_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return file_data, filename


def _export_to_pdf(items, user_permissions=None):
    """Export items to PDF format with user permission filtering - returns (file_data, filename)"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    from reportlab.lib import colors

    # Get user permissions
    can_see_buying_price = True
    can_see_profit = True

    if user_permissions:
        can_see_buying_price = user_permissions.get("can_see_buying_price", True)
        can_see_profit = user_permissions.get("can_see_profit_margin", True)

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title = Paragraph("<b>Items Export</b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Create table headers based on permissions
    headers = ["Item No", "Item Name", "Category", "Type", "Unit Price"]

    # Add Unit Cost column only if user has permission
    if can_see_buying_price:
        headers.append("Unit Cost")

    # Add Profit Margin column only if user has permission
    if can_see_profit:
        headers.append("Profit %")

    headers.extend(["Inventory", "Status"])

    data = [headers]

    for item in items[:500]:  # Limit to 500 items for PDF
        row = [
            item.no or "",
            item.item_name or "",
            item.item_category.description if item.item_category else "",
            item.type or "",
            f"{format_currency(item.unit_price)}" if item.unit_price else format_currency(0),
        ]

        # Add Unit Cost only if user has permission (branch-scoped when annotated)
        if can_see_buying_price:
            unit_cost = _export_item_unit_cost(item)
            row.append(
                f"{format_currency(unit_cost)}" if unit_cost else format_currency(0)
            )

        # Add Profit Margin only if user has permission (branch-scoped when annotated)
        if can_see_profit:
            profit = _export_item_profit_pct(item)
            row.append(f"{profit:.2f}%")

        row.extend(
            [
                str(_export_item_inventory(item)),
                "Active" if not item.blocked else "Blocked",
            ]
        )

        data.append(row)

    # Create table
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)
    output.seek(0)

    filename = f"items_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return output.read(), filename


@shared_task(bind=True)
def calculate_inventory_task(
    self,
    posting_date,
    location_filter=None,
    item_filter=None,
    include_zero_quantity=False,
    journal_template="PHYS. INV.",
    journal_batch="DEFAULT",
    user_id=None,
    schema_name=None,
    branch_id=None,
):
    """
    Background task to calculate inventory and populate journal lines for physical inventory.

    Args:
        self: Task instance
        posting_date: Date string for posting
        location_filter: Optional location ID to filter by
        item_filter: Optional item number to filter by
        journal_template: Template name (default: "PHYS. INV.")
        journal_batch: Batch name (default: "DEFAULT")
        user_id: User ID who initiated the calculation
        schema_name: Tenant schema name

    Returns:
        dict: Result with created_count, deleted_count, and journal_ids
    """
    logger = get_task_logger(__name__)

    try:
        from items.models import (
            ItemJournalTemplate,
            ItemJournalBatch,
            ItemLedgerEntries,
            Item,
            ValueEntry,
            ItemJournal,
            ItemUnitOfMeasure,
        )
        from django.db.models import Sum
        from helpers.helpers import increment_item_number
        from setup.models import NoSeriesLines, JournalSetup
        from dimension.models import get_posting_dimension_payload, DimensionValue
        from common.enums import Status
        from datetime import datetime
        import uuid
        from django_tenants.utils import schema_context

        schema_name = schema_name or connection.schema_name

        with schema_context(schema_name):
            # Get user
            user = User.objects.get(pk=user_id) if user_id else None
            # Resolve posting dimensions (selected branch first, then user branch).
            branch_value = None
            if branch_id:
                try:
                    branch_value = DimensionValue.objects.filter(pk=int(branch_id)).first()
                except Exception:
                    branch_value = None
            if not branch_value and user is not None:
                branch_value = getattr(user, "global_dimension_1", None)
            dim_payload = get_posting_dimension_payload(global_dimension_1=branch_value)

            # Get or create template (PHYS. INV.)
            template, _ = ItemJournalTemplate.objects.get_or_create(
                name=journal_template,
                defaults={
                    "description": "Physical Inventory",
                    "type": "phys_inventory",
                },
            )

            # Get or create batch
            batch, _ = ItemJournalBatch.objects.get_or_create(
                journal_template=template,
                name=journal_batch,
                defaults={"description": "Default Journal"},
            )

            # Delete all existing journals in this batch before creating new ones
            existing_journals = ItemJournal.objects.filter(
                journal_template=template, journal_batch=batch, status=Status.Open.value
            )
            deleted_count = existing_journals.count()
            existing_journals.delete()

            # Build query for items
            items_query = Item.objects.filter(type="Inventory")

            if item_filter:
                items_query = items_query.filter(no=item_filter)

            # Build query for inventory calculation
            ledger_query = ItemLedgerEntries.objects.filter(
                item__in=items_query, remaining_quantity__gt=0
            )

            if location_filter:
                ledger_query = ledger_query.filter(location_id=location_filter)

            # Group by item and location to get calculated quantities
            inventory_data = list(ledger_query.values("item", "location").annotate(
                calculated_qty=Sum("remaining_quantity")
            ))

            if include_zero_quantity:
                existing_item_ids = {entry["item"] for entry in inventory_data}
                all_item_ids = list(items_query.values_list("no", flat=True))
                target_location = int(location_filter) if location_filter else None
                for item_id in all_item_ids:
                    if item_id in existing_item_ids:
                        continue
                    inventory_data.append(
                        {"item": item_id, "location": target_location, "calculated_qty": 0}
                    )

            created_journals = []
            journal_ids = []

            total_items = len(inventory_data)
            for idx, data in enumerate(inventory_data):
                # Update task progress
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": idx + 1,
                        "total": total_items,
                        "status": f"Processing item {idx + 1} of {total_items}",
                    },
                )

                # Item model uses 'no' as primary key
                item = Item.objects.get(pk=data["item"])
                location_id = data["location"]

                # Get unit cost from latest value entry or item
                latest_value = (
                    ValueEntry.objects.filter(item=item).order_by("-created_at").first()
                )

                unit_cost = (
                    latest_value.cost_per_unit
                    if latest_value and latest_value.cost_per_unit
                    else item.manual_unit_cost or 0
                )

                # Generate document number
                document_no = None
                if template.no_series:
                    journal_no_series = NoSeriesLines.objects.filter(
                        no_series=template.no_series
                    ).first()
                    if journal_no_series:
                        increment_by = journal_no_series.increment_by
                        if journal_no_series.last_used_number:
                            document_no = increment_item_number(
                                journal_no_series.last_used_number, increment_by
                            )
                            journal_no_series.last_used_number = document_no
                            journal_no_series.last_used_date = datetime.now()
                            journal_no_series.save()
                        else:
                            document_no = journal_no_series.start_number
                            journal_no_series.last_used_number = document_no
                            journal_no_series.last_used_date = datetime.now()
                            journal_no_series.save()

                # Fallback to JournalSetup
                if not document_no and JournalSetup.objects.all().first():
                    journal_no_series = NoSeriesLines.objects.filter(
                        no_series=JournalSetup.objects.all().first().journal_no_series
                    ).first()
                    if journal_no_series:
                        increment_by = journal_no_series.increment_by
                        if journal_no_series.last_used_number:
                            document_no = increment_item_number(
                                journal_no_series.last_used_number, increment_by
                            )
                            journal_no_series.last_used_number = document_no
                            journal_no_series.last_used_date = datetime.now()
                            journal_no_series.save()
                        else:
                            document_no = journal_no_series.start_number
                            journal_no_series.last_used_number = document_no
                            journal_no_series.last_used_date = datetime.now()
                            journal_no_series.save()

                # Final fallback
                if not document_no:
                    document_no = f"PHYS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

                calculated_qty = int(data.get("calculated_qty") or 0)

                # Use the item's base (default) unit of measure for stock taking
                base_uom = ItemUnitOfMeasure.objects.filter(
                    item=item, default=True
                ).first()
                if not base_uom:
                    base_uom = ItemUnitOfMeasure.objects.filter(item=item).first()

                journal = ItemJournal.objects.create(
                    journal_template=template,
                    journal_batch=batch,
                    item=item,
                    item_unit_of_measure=base_uom,
                    entry_type="PositiveAdjustment",  # Will be updated by save() method based on difference
                    document_no=document_no,
                    description=f"Physical inventory for {item.item_name}",
                    calculated_quantity=calculated_qty,
                    physical_quantity=calculated_qty,  # Initially set to calculated quantity, user can change it
                    quantity=0,  # Will be set by save() method based on difference
                    location_code_id=location_id if location_id else None,
                    date=posting_date,
                    unit_cost=unit_cost,
                    user=user,
                    status=Status.Open.value,
                    global_dimension_1=dim_payload.get("global_dimension_1"),
                    global_dimension_2=dim_payload.get("global_dimension_2"),
                    dimension_set=dim_payload.get("dimension_set"),
                )
                created_journals.append(journal)
                journal_ids.append(journal.id)

            return {
                "success": True,
                "deleted_count": deleted_count,
                "created_count": len(created_journals),
                "journal_ids": journal_ids,
                "message": f"Successfully calculated inventory. Created {len(created_journals)} journal entries.",
            }

    except Exception as e:
        logger.error(f"Calculate inventory failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to calculate inventory: {str(e)}",
        }


@shared_task(bind=True)
def export_stock_taking_task(
    self,
    show_calculated_qty=False,
    show_tracking_numbers=False,
    show_location_code=False,
    include_unit_cost=False,
    include_zero_quantity=True,
    location_filter=None,
    schema_name=None,
    user_id=None,
):
    """
    Background task to export stock taking journals to Excel format
    Args:
        self: Task instance
        show_calculated_qty: Include calculated quantity column
        show_tracking_numbers: Include item tracking numbers
        show_location_code: Include location code column
        location_filter: Optional location ID to filter by (if None, exports all)
        schema_name: Schema name for tenant
        user_id: User ID who triggered the export
    """
    logger = get_task_logger(__name__)

    try:
        from django_tenants.utils import schema_context
        from django.db import connection
        import xlsxwriter
        from datetime import datetime

        schema_name = schema_name or connection.schema_name

        with schema_context(schema_name):
            # Update initial status
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 10,
                    "message": "Preparing export...",
                    "status": "processing",
                },
            )

            # Filter journals by template "PHYS. INV." and batch "DEFAULT"
            queryset = ItemJournal.objects.filter(
                journal_template__name="PHYS. INV.", journal_batch__name="DEFAULT"
            )

            if not include_zero_quantity:
                queryset = queryset.exclude(calculated_quantity=0)

            # Apply location filter if specified
            if location_filter:
                queryset = queryset.filter(location_code_id=location_filter)

            queryset = queryset.select_related(
                "item", "location_code", "journal_template", "journal_batch"
            ).prefetch_related("item_journal_tracking_specifications")

            # Evaluate queryset
            journals = list(queryset)
            total_journals = len(journals)

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 30,
                    "message": f"Exporting {total_journals} journals...",
                    "status": "processing",
                },
            )

            # Create BytesIO buffer for the Excel file
            output = BytesIO()

            # Create workbook
            workbook = xlsxwriter.Workbook(output, {"strings_to_urls": False})
            worksheet = workbook.add_worksheet("Stock Taking")

            from items.models import ItemLedgerEntries, Location
            from django.db.models import Sum

            # Workbook layout formats (Arial across sheet)
            title_format = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bold": True,
                    "font_size": 13,
                    "bg_color": "#1F3864",
                    "font_color": "#FFFFFF",
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            instruction_format = workbook.add_format(
                {
                    "font_name": "Arial",
                    "italic": True,
                    "font_size": 9,
                    "bg_color": "#EBF3FB",
                    "align": "left",
                    "valign": "vcenter",
                }
            )
            header_format = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": "#1F3864",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            )
            item_cell_center = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#D6E4F7",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            item_cell_bold_center = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#D6E4F7",
                    "border": 1,
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            item_desc_bold = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#D6E4F7",
                    "border": 1,
                    "bold": True,
                    "align": "left",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            )
            blank_cell = workbook.add_format(
                {"font_name": "Arial", "border": 1, "align": "left", "valign": "vcenter"}
            )
            blue_tint_center = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#EBF3FB",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            yellow_input = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#FFFFC0",
                    "bold": True,
                    "font_size": 10,
                    "font_color": "#CC0000",
                    "border": 2,
                    "border_color": "#CC6600",
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            pink_formula = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#FFF5F5",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            separator_cell = workbook.add_format(
                {"font_name": "Arial", "bg_color": "#D0D0D0", "border": 0}
            )
            legend_format = workbook.add_format(
                {
                    "font_name": "Arial",
                    "bg_color": "#EEEEEE",
                    "italic": True,
                    "font_size": 8,
                    "align": "left",
                    "valign": "vcenter",
                }
            )

            # Column widths (A-I + optional Unit Cost)
            widths = [12, 14, 42, 14, 18, 13, 14, 13, 18]
            if include_unit_cost:
                widths.append(12)
            for col_idx, width in enumerate(widths):
                worksheet.set_column(col_idx, col_idx, width)
            last_col = len(widths) - 1

            # Banner rows + headers
            tenant_name = (
                getattr(getattr(connection, "tenant", None), "name", None)
                or schema_name
                or "TENANT"
            )
            location_label = "ALL LOCATIONS"
            if location_filter:
                loc = Location.objects.filter(pk=location_filter).first()
                if loc:
                    location_label = f"{loc.code} - {loc.description}"

            title_text = (
                f"{tenant_name} / {location_label} — STOCK TAKING PHYSICAL COUNT SHEET"
            )
            worksheet.merge_range(
                0, 0, 0, last_col, title_text, title_format
            )
            today_str = datetime.now().strftime("%Y-%m-%d")
            instruction_text = (
                f"Date: {today_str}   Instructions: Enter the ACTUAL COUNTED QTY for each lot in the yellow column. "
                "Leave blank if not counted yet."
            )
            worksheet.merge_range(1, 0, 1, last_col, instruction_text, instruction_format)
            headers = [
                "Posting Date",
                "Item No.",
                "Description",
                "System Total (Calculated)",
                "Lot Number",
                "Qty per Lot (System)",
                "★ Qty Counted (Physical) ★",
                "Difference (Counted-System)",
                "Remarks",
            ]
            if include_unit_cost:
                headers.append("Unit Cost")
            for col_idx, header in enumerate(headers):
                worksheet.write(2, col_idx, header, header_format)

            worksheet.set_row(0, 28)
            worksheet.set_row(1, 18)
            worksheet.set_row(2, 36)

            # Sheet UX + print settings
            worksheet.freeze_panes(3, 0)  # freeze top 3 rows; data starts on row 4
            worksheet.set_landscape()
            worksheet.fit_to_pages(1, 0)
            worksheet.repeat_rows(0, 2)

            # Data rows start at Excel row 4 (0-index row 3)
            row_idx = 3
            for journal_index, journal in enumerate(journals, start=1):
                ledger_query = ItemLedgerEntries.objects.filter(
                    item=journal.item, remaining_quantity__gt=0
                )
                if journal.location_code:
                    ledger_query = ledger_query.filter(location=journal.location_code)

                lot_data = (
                    ledger_query.exclude(lot_no__isnull=True)
                    .exclude(lot_no="")
                    .values("lot_no")
                    .annotate(quantity_base=Sum("remaining_quantity"))
                    .order_by("lot_no")
                )
                lots = list(lot_data)
                if not lots:
                    lots = [
                        {
                            "lot_no": "",
                            "quantity_base": (
                                journal.calculated_quantity
                                if journal.calculated_quantity is not None
                                else 0
                            ),
                        }
                    ]

                system_total = (
                    journal.calculated_quantity
                    if journal.calculated_quantity is not None
                    else sum(int(l.get("quantity_base") or 0) for l in lots)
                )

                for lot_idx, lot_entry in enumerate(lots):
                    worksheet.set_row(row_idx, 18)
                    excel_row = row_idx + 1

                    if lot_idx == 0:
                        worksheet.write(
                            row_idx,
                            0,
                            journal.date.strftime("%Y-%m-%d") if journal.date else "",
                            item_cell_center,
                        )
                        worksheet.write(
                            row_idx,
                            1,
                            journal.item.no if journal.item else "",
                            item_cell_bold_center,
                        )
                        worksheet.write(
                            row_idx,
                            2,
                            journal.item.item_name if journal.item else "",
                            item_desc_bold,
                        )
                        worksheet.write(row_idx, 3, int(system_total or 0), item_cell_bold_center)
                    else:
                        worksheet.write(row_idx, 0, "", blank_cell)
                        worksheet.write(row_idx, 1, "", blank_cell)
                        worksheet.write(row_idx, 2, "", blank_cell)
                        worksheet.write(row_idx, 3, "", blank_cell)

                    worksheet.write(row_idx, 4, lot_entry.get("lot_no") or "", blue_tint_center)
                    worksheet.write(
                        row_idx,
                        5,
                        int(lot_entry.get("quantity_base") or 0),
                        blue_tint_center,
                    )
                    worksheet.write(row_idx, 6, "", yellow_input)
                    worksheet.write_formula(
                        row_idx,
                        7,
                        f'=IF(G{excel_row}="","",G{excel_row}-F{excel_row})',
                        pink_formula,
                    )
                    worksheet.write(row_idx, 8, "", blank_cell)
                    if include_unit_cost:
                        worksheet.write(
                            row_idx,
                            9,
                            float(journal.unit_cost or 0),
                            blue_tint_center,
                        )
                    row_idx += 1

                if len(lots) > 1:
                    worksheet.set_row(row_idx, 4)
                    for col_idx in range(len(widths)):
                        worksheet.write(row_idx, col_idx, "", separator_cell)
                    row_idx += 1

                if journal_index % 25 == 0:
                    progress = 30 + int((journal_index / max(total_journals, 1)) * 50)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": progress,
                            "message": f"Exported {journal_index} of {total_journals} journals...",
                            "status": "processing",
                        },
                    )

            # Legend row
            legend_text = (
                "LEGEND:   Light blue = Item header row   |   Yellow = Enter physical count here   |   "
                "Col H auto-calculates difference (negative = shortage, positive = surplus)"
            )
            worksheet.merge_range(row_idx, 0, row_idx, last_col, legend_text, legend_format)

            # Close workbook
            workbook.close()

            # Get file data
            output.seek(0)
            file_data = output.read()

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 90,
                    "message": "Finalizing export...",
                    "status": "processing",
                },
            )

            # Encode file data to base64 for storage in cache
            file_data_base64 = base64.b64encode(file_data).decode("utf-8")

            # Store in cache with task_id and schema_name as key (expires in 2 hours)
            task_id_str = str(self.request.id)
            cache_key = f"export_stock_taking_{schema_name}_{task_id_str}"

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stock_taking_export_{timestamp}.xlsx"

            file_info = {
                "file_data": file_data_base64,
                "filename": filename,
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }

            # Store in cache with 2-hour timeout
            cache.set(cache_key, file_info, timeout=7200)

            return {
                "success": True,
                "message": f"Export completed successfully. {total_journals} journals exported.",
                "status": "completed",
                "progress": 100,
                "filename": filename,
                "task_id": task_id_str,
                "cache_key": cache_key,
                "schema_name": schema_name,
                "total_journals": total_journals,
            }

    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Export failed: {str(e)}",
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }


@shared_task(bind=True)
def import_stock_taking_task(
    self,
    file_path,
    schema_name=None,
    user_id=None,
):
    """
    Background task to import physical quantities from Excel/CSV file
    Args:
        self: Task instance
        file_path: Path to the uploaded file
        schema_name: Schema name for tenant
        user_id: User ID who triggered the import
    """
    logger = get_task_logger(__name__)

    try:
        from django_tenants.utils import schema_context
        from django.db import connection
        import os

        schema_name = schema_name or connection.schema_name

        with schema_context(schema_name):
            # Update initial status
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 10,
                    "message": "Reading file...",
                    "status": "processing",
                },
            )

            # Read file based on extension
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in [".xlsx", ".xls"]:
                # Read raw first so we can auto-detect the actual header row.
                raw_df = pd.read_excel(file_path, header=None)
                header_row_idx = 0
                for idx in range(min(len(raw_df), 20)):
                    row_values = [
                        str(v).strip().lower()
                        for v in raw_df.iloc[idx].tolist()
                        if pd.notna(v) and str(v).strip()
                    ]
                    if any(
                        token in row_values
                        for token in ("item no.", "item no", "item", "lot number", "lot no.")
                    ):
                        header_row_idx = idx
                        break
                df = pd.read_excel(file_path, header=header_row_idx)
            elif file_ext == ".csv":
                df = pd.read_csv(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            total_rows = len(df)
            if total_rows == 0:
                raise ValueError("File is empty")

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 20,
                    "message": f"Processing {total_rows} rows...",
                    "status": "processing",
                },
            )

            # Normalize column names (handle variations)
            column_mapping = {
                "item no": "item_no",
                "item_no": "item_no",
                "item": "item_no",
                "item no.": "item_no",
                "posting date": "posting_date",
                "description": "description",
                "physical qty": "physical_quantity",
                "physical_quantity": "physical_quantity",
                "physical qty.": "physical_quantity",
                "qty. (phys. inventory)": "physical_quantity",
                "qty (phys inventory)": "physical_quantity",
                "qty counted (physical)": "qty_counted_physical",
                "qty counted physical": "qty_counted_physical",
                "qty counted": "qty_counted_physical",
                "★ qty counted (physical) ★": "qty_counted_physical",
                "qty. (phys. inventory) per lot": "phys_qty_per_lot",
                "qty (phys inventory) per lot": "phys_qty_per_lot",
                "phys_qty_per_lot": "phys_qty_per_lot",
                "lot no": "lot_no",
                "lot_no": "lot_no",
                "lot no.": "lot_no",
                "lot number": "lot_no",
                "quantity (base)": "quantity_base",
                "quantity_base": "quantity_base",
                "difference (counted-system)": "difference",
                "difference": "difference",
                "remarks": "remarks",
                "location code": "location_code",
                "location_code": "location_code",
                "location": "location_code",
            }

            df.columns = df.columns.str.lower().str.strip()
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)

            # Validate required columns
            if "item_no" not in df.columns:
                raise ValueError("Required column 'Item No.' not found in file")

            has_physical_col = "physical_quantity" in df.columns
            has_counted_col = "qty_counted_physical" in df.columns
            has_per_lot_col = "phys_qty_per_lot" in df.columns
            if not (has_physical_col or has_counted_col or has_per_lot_col):
                raise ValueError(
                    "Required counted quantity column not found. Expected one of: "
                    "'★ Qty Counted (Physical) ★', 'Qty. (Phys. Inventory)', or 'Qty. (Phys. Inventory) per Lot'"
                )

            # Statistics
            updated_count = 0
            failed_count = 0
            errors = []
            current_journal = None

            def _parse_qty(val):
                try:
                    return int(float(val)) if pd.notna(val) and val != "" else 0
                except (ValueError, TypeError):
                    return 0

            def _parse_optional_qty(val):
                if pd.isna(val) or val is None:
                    return None
                s = str(val).strip()
                if not s or s.lower() in ("nan", "none", "nat"):
                    return None
                try:
                    return int(float(s))
                except (ValueError, TypeError):
                    return None

            def _normalize_cell(val):
                """Treat NaN, 'nan', and empty as blank for Item No. / Lot No."""
                if pd.isna(val) or val is None:
                    return ""
                s = str(val).strip()
                if s.lower() in ("nan", "none", "nat"):
                    return ""
                # Excel often loads numeric lot values as floats (e.g., 586220706.0).
                # Normalize integral floats back to plain integer-like strings.
                try:
                    n = float(s)
                    if n.is_integer():
                        return str(int(n))
                except (ValueError, TypeError):
                    pass
                return s

            def _sync_journal_phys_qty_from_lots(journal):
                """Set journal.physical_quantity from sum of TrackingSpecification for lot-tracked items."""
                if not journal or not journal.item:
                    return
                tracking_code = getattr(journal.item, "tracking_code", None)
                if not tracking_code or not getattr(
                    tracking_code, "require_lot_no", False
                ):
                    return
                specs = TrackingSpecification.objects.filter(item_journal=journal)
                total = sum(s.quantity_base for s in specs)
                journal.physical_quantity = total
                journal.save()

            # Process each row
            for index, row in df.iterrows():
                try:
                    item_no = _normalize_cell(
                        row.get("item_no", "") if "item_no" in df.columns else ""
                    )
                    lot_no = (
                        _normalize_cell(row.get("lot_no", ""))
                        if "lot_no" in df.columns
                        else ""
                    )
                    counted_qty = _parse_optional_qty(
                        row.get("qty_counted_physical")
                        if "qty_counted_physical" in df.columns
                        else row.get("physical_quantity")
                    )
                    physical_qty = (
                        counted_qty
                        if counted_qty is not None
                        else _parse_optional_qty(row.get("physical_quantity"))
                    )
                    phys_qty_per_lot = (
                        row.get("phys_qty_per_lot")
                        if "phys_qty_per_lot" in df.columns
                        else None
                    )
                    phys_qty_per_lot = _parse_optional_qty(phys_qty_per_lot)
                    if phys_qty_per_lot is None:
                        phys_qty_per_lot = counted_qty
                    location_code = (
                        _normalize_cell(row.get("location_code", ""))
                        if "location_code" in df.columns
                        else None
                    )
                    location_code = location_code or None

                    if item_no and item_no.upper().startswith("LEGEND:"):
                        continue

                    if item_no:
                        # Main row: find journal, update physical_quantity, set current_journal
                        if current_journal:
                            _sync_journal_phys_qty_from_lots(current_journal)
                            current_journal = None

                        journal_filter = {
                            "journal_template__name": "PHYS. INV.",
                            "journal_batch__name": "DEFAULT",
                            "item__no": item_no,
                        }
                        if location_code:
                            journal_filter["location_code__code"] = location_code

                        journal = ItemJournal.objects.filter(**journal_filter).first()
                        if not journal:
                            failed_count += 1
                            errors.append(
                                f"Row {index + 2}: Journal not found for Item No. '{item_no}'"
                                + (
                                    f" and Location '{location_code}'"
                                    if location_code
                                    else ""
                                )
                            )
                            continue

                        tracking_code = getattr(journal.item, "tracking_code", None)
                        is_lot_tracked = (
                            tracking_code
                            and getattr(tracking_code, "require_lot_no", False)
                        )
                        if not is_lot_tracked:
                            if physical_qty is None:
                                continue
                            journal.physical_quantity = physical_qty
                            journal.save()
                        else:
                            current_journal = journal
                            # New template stores Item No. + Lot Number on the same row.
                            # Apply that lot row immediately instead of waiting for a sub-row.
                            if lot_no and phys_qty_per_lot is not None:
                                TrackingSpecification.objects.update_or_create(
                                    item_journal=current_journal,
                                    lot_no=lot_no,
                                    defaults={
                                        "item": current_journal.item,
                                        "quantity_base": phys_qty_per_lot,
                                        "location_code": current_journal.location_code,
                                        "description": f"Stock taking - Lot {lot_no}",
                                    },
                                )

                        updated_count += 1
                    elif lot_no and current_journal:
                        # Lot sub-row: create/update TrackingSpecification
                        qty = phys_qty_per_lot
                        if qty is None:
                            continue

                        TrackingSpecification.objects.update_or_create(
                            item_journal=current_journal,
                            lot_no=lot_no,
                            defaults={
                                "item": current_journal.item,
                                "quantity_base": qty,
                                "location_code": current_journal.location_code,
                                "description": f"Stock taking - Lot {lot_no}",
                            },
                        )
                        updated_count += 1
                    elif not item_no and not lot_no:
                        # Skip separator/empty/decorative rows
                        continue

                    if (index + 1) % 10 == 0:
                        progress = 20 + int(((index + 1) / total_rows) * 70)
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "progress": progress,
                                "message": f"Processed {index + 1} of {total_rows} rows...",
                                "status": "processing",
                            },
                        )

                except Exception as e:
                    failed_count += 1
                    error_msg = f"Row {index + 2}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

            if current_journal:
                _sync_journal_phys_qty_from_lots(current_journal)

            # Clean up temp file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {str(e)}")

            return {
                "success": True,
                "message": f"Import completed. Updated: {updated_count}, Failed: {failed_count}",
                "status": "completed",
                "progress": 100,
                "updated_count": updated_count,
                "failed_count": failed_count,
                "total_rows": total_rows,
                "errors": errors[:100],  # Limit to first 100 errors
            }

    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Import failed: {str(e)}",
            "status": "failed",
            "progress": 0,
            "error": str(e),
        }
