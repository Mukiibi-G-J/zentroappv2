"""
Reverse posted item journal ledger rows (G/L, item ledger, value entries) and restore FIFO.

Used to undo mis-posted journals (e.g. duplicate value entries on lot-tracked negative adjustments)
before re-posting a corrected journal line.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from financials.models import GeneralLedgerEntry
from items.enums import EntryType
from items.models import (
    ItemJournal,
    ItemLedgerEntries,
    ItemUnitOfMeasure,
    TrackingSpecification,
    ValueEntry,
)


def _ledger_line_override_keys() -> frozenset[str]:
    return frozenset({"quantity", "total", "remaining_quantity"})


def merge_tracked_ledger_additional_fields(
    base_fields: dict[str, Any], additional_fields: dict[str, Any]
) -> None:
    """Apply journal-level overrides only when not splitting by tracking spec."""
    outbound = additional_fields.get("quantity", 0) < 0
    if outbound:
        safe = {
            k: v
            for k, v in additional_fields.items()
            if k not in _ledger_line_override_keys()
        }
        base_fields.update(safe)
        if "remaining_quantity" in additional_fields:
            base_fields["remaining_quantity"] = additional_fields["remaining_quantity"]
    else:
        base_fields.update(additional_fields)


def build_tracked_line_quantity_and_total(
    spec_quantity: int,
    journal_quantity: int,
    journal_total: float,
    additional_fields: dict[str, Any],
) -> tuple[int, float]:
    spec_total = (
        (spec_quantity / journal_quantity) * journal_total
        if journal_quantity > 0
        else 0.0
    )
    if additional_fields.get("quantity", 0) < 0:
        return -int(spec_quantity), -float(spec_total)
    return int(spec_quantity), float(spec_total)


def _rows_needing_reversal(queryset, *, child_model, reverses_field: str):
    """
    Rows to reverse: unreversed first; else reversed rows with no reversing child yet.
    """
    pending = list(queryset.filter(reversed=False).order_by("id"))
    if pending:
        return pending

    reversed_rows = list(queryset.filter(reversed=True).order_by("id"))
    if not reversed_rows:
        return []

    parent_ids = [row.id for row in reversed_rows]
    linked_parent_ids = set(
        child_model.objects.filter(**{f"{reverses_field}__in": parent_ids}).values_list(
            reverses_field, flat=True
        )
    )
    return [row for row in reversed_rows if row.id not in linked_parent_ids]


class ItemJournalPostingReversal:
    def __init__(
        self,
        *,
        journal: ItemJournal,
        user,
        reversal_document_no: str | None = None,
        reversal_date: date | None = None,
    ):
        self.journal = journal
        self.user = user
        self.reversal_document_no = (
            reversal_document_no or f"{journal.document_no}-REV"
        )
        self.reversal_date = reversal_date or journal.date or timezone.now().date()
        self.transaction_no = (
            f"REV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

    def _original_gl_queryset(self):
        return GeneralLedgerEntry.objects.filter(document_no=self.journal.document_no)

    def _original_ile_queryset(self):
        return ItemLedgerEntries.objects.filter(document_no=self.journal.document_no)

    def _original_ve_queryset(self):
        return ValueEntry.objects.filter(document_no=self.journal.document_no)

    def _reversal_ile_exists(self) -> bool:
        return ItemLedgerEntries.objects.filter(
            document_no=self.reversal_document_no
        ).exists()

    def _reversal_ve_exists(self) -> bool:
        return ValueEntry.objects.filter(document_no=self.reversal_document_no).exists()

    def _collect_gl_rows(self):
        return _rows_needing_reversal(
            self._original_gl_queryset(),
            child_model=GeneralLedgerEntry,
            reverses_field="reverses_entry_no",
        )

    def _collect_ile_rows(self):
        all_rows = list(self._original_ile_queryset().order_by("id"))
        pending = _rows_needing_reversal(
            self._original_ile_queryset(),
            child_model=ItemLedgerEntries,
            reverses_field="reverses_entry_no",
        )
        if not pending:
            return []
        if self._reversal_ile_exists():
            return []
        if self._use_consolidated_inventory_reversal(all_rows):
            return all_rows
        return pending

    def _collect_ve_rows(self):
        all_rows = list(self._original_ve_queryset().order_by("id"))
        pending = _rows_needing_reversal(
            self._original_ve_queryset(),
            child_model=ValueEntry,
            reverses_field="reverses_value_entry_no",
        )
        if not pending:
            return []
        if self._reversal_ve_exists():
            return []
        if self._use_consolidated_inventory_reversal(
            list(self._original_ile_queryset().order_by("id"))
        ):
            return all_rows
        return pending

    def dry_run_plan(self) -> dict[str, Any]:
        gl = self._collect_gl_rows()
        ile = self._collect_ile_rows()
        ve = self._collect_ve_rows()
        fifo_restore = (
            [] if ile else self._plan_fifo_restore()
        )
        return {
            "journal_id": self.journal.id,
            "document_no": self.journal.document_no,
            "reversal_document_no": self.reversal_document_no,
            "transaction_no": self.transaction_no,
            "gl_entries": [
                {
                    "id": e.id,
                    "account": e.gl_account.name,
                    "amount": e.amount,
                    "reversal_amount": -e.amount,
                }
                for e in gl
            ],
            "item_ledger_entries": self._preview_ile_reversal_rows(ile),
            "value_entries": self._preview_ve_reversal_rows(ve),
            "fifo_restore": fifo_restore,
            "can_reverse": self.journal.status == "Posted"
            and bool(gl or ile or ve),
            "mode": (
                "create_reversing_entries"
                if gl or ile or ve
                else "nothing_pending"
            ),
        }

    def _preview_ile_reversal_rows(self, ile: list) -> list[dict[str, Any]]:
        if self._use_consolidated_inventory_reversal(ile):
            base_qty = self._journal_base_quantity()
            return [
                {
                    "id": "consolidated",
                    "quantity": f"sum of {len(ile)} lines",
                    "total": self.journal.amount,
                    "lot_no": "(journal total)",
                    "reversal_quantity": base_qty,
                    "reversal_total": float(self.journal.amount or 0),
                }
            ]
        return [
            {
                "id": e.id,
                "quantity": e.quantity,
                "total": e.total,
                "lot_no": e.lot_no,
                "reversal_quantity": -e.quantity,
                "reversal_total": -(e.total or 0),
            }
            for e in ile
        ]

    def _preview_ve_reversal_rows(self, ve: list) -> list[dict[str, Any]]:
        all_ile = list(self._original_ile_queryset().order_by("id"))
        if self._use_consolidated_inventory_reversal(all_ile) and ve:
            from items.value_entry_posting import bc_normalize_value_entry_fields

            signs = bc_normalize_value_entry_fields(
                EntryType.PositiveAdjustment.name,
                self._journal_base_quantity(),
                float(self.journal.amount or 0),
                cost_per_unit=ve[0].cost_per_unit,
            )
            return [
                {
                    "id": "consolidated",
                    "qty": f"sum of {len(ve)} lines",
                    "cost": self.journal.amount,
                    "reversal_qty": signs["item_ledger_entry_quantity"],
                    "reversal_cost": signs["cost_amount"],
                    "reversal_entry_type": EntryType.PositiveAdjustment.name,
                }
            ]
        return [self._preview_ve_reversal_row(e) for e in ve]

    def _preview_ve_reversal_row(self, entry: ValueEntry) -> dict[str, Any]:
        signs = self._reversal_value_entry_signs(entry)
        return {
            "id": entry.id,
            "qty": entry.item_ledger_entry_quantity,
            "cost": entry.cost_amount,
            "reversal_qty": signs["item_ledger_entry_quantity"],
            "reversal_cost": signs["cost_amount"],
            "reversal_entry_type": signs["entry_type"],
        }

    @staticmethod
    def _reversal_value_entry_signs(original: ValueEntry) -> dict[str, Any]:
        from items.value_entry_posting import bc_normalize_value_entry_fields

        qty_abs = abs(int(original.item_ledger_entry_quantity or 0))
        cost_abs = abs(float(original.cost_amount or 0))
        if original.entry_type == EntryType.NegativeAdjustment.name:
            rev_type = EntryType.PositiveAdjustment.name
        elif original.entry_type == EntryType.PositiveAdjustment.name:
            rev_type = EntryType.NegativeAdjustment.name
        else:
            rev_type = original.entry_type
        signs = bc_normalize_value_entry_fields(
            rev_type,
            qty_abs,
            cost_abs,
            cost_per_unit=original.cost_per_unit,
        )
        signs["entry_type"] = rev_type
        return signs

    def _journal_base_quantity(self) -> int:
        try:
            uom = ItemUnitOfMeasure.objects.get(
                id=self.journal.item_unit_of_measure_id
            )
            return int(uom.quantity_per_unit) * int(self.journal.quantity or 0)
        except ItemUnitOfMeasure.DoesNotExist:
            return int(self.journal.quantity or 0)

    def _use_consolidated_inventory_reversal(self, ile_rows: list) -> bool:
        """Duplicate lot lines from one journal should reverse once at journal totals."""
        return (
            self.journal.entry_type == EntryType.NegativeAdjustment.name
            and len(ile_rows) > 1
        )

    def _plan_fifo_restore(self) -> list[dict[str, Any]]:
        if self.journal.entry_type != EntryType.NegativeAdjustment.name:
            return []

        specs = (
            TrackingSpecification.objects.filter(item_journal=self.journal)
            .exclude(lot_no__isnull=True)
            .exclude(lot_no="")
            .order_by("id")
        )
        restores: list[dict[str, Any]] = []
        if specs.exists():
            for spec in specs:
                qty = int(spec.quantity_base or 0)
                if qty <= 0:
                    continue
                restores.append(
                    {
                        "method": "tracking_lot",
                        "lot_no": spec.lot_no,
                        "quantity_to_restore": qty,
                    }
                )
            return restores

        try:
            uom = ItemUnitOfMeasure.objects.get(
                id=self.journal.item_unit_of_measure_id
            )
            base_qty = int(uom.quantity_per_unit) * int(self.journal.quantity or 0)
        except ItemUnitOfMeasure.DoesNotExist:
            base_qty = int(self.journal.quantity or 0)
        if base_qty > 0:
            restores.append(
                {"method": "fifo_base", "quantity_to_restore": base_qty}
            )
        return restores

    @transaction.atomic
    def apply(self, *, mark_only: bool = False) -> dict[str, Any]:
        if self.journal.status != "Posted":
            raise ValueError(
                f"Journal {self.journal.document_no} is not Posted (status={self.journal.status})."
            )

        gl_rows = self._collect_gl_rows()
        if gl_rows:
            gl_rows = list(
                GeneralLedgerEntry.objects.filter(
                    id__in=[r.id for r in gl_rows]
                ).select_related("gl_account")
            )
        ile_rows = self._collect_ile_rows()
        ve_ids = [r.id for r in self._collect_ve_rows()]
        ve_rows = list(
            ValueEntry.objects.filter(id__in=ve_ids).select_related(
                "item_ledger_entry_no",
                "general_product_posting_group",
                "inventory_posting_group",
                "global_dimension_1",
                "dimension_set",
            )
        ) if ve_ids else []

        if not gl_rows and not ile_rows and not ve_rows:
            raise ValueError(
                f"No ledger rows pending reversal for document {self.journal.document_no} "
                "(already fully reversed with reversing entries)."
            )

        if mark_only:
            gl_rows = list(
                GeneralLedgerEntry.objects.filter(
                    document_no=self.journal.document_no, reversed=False
                )
            )
            ile_rows = list(
                ItemLedgerEntries.objects.filter(
                    document_no=self.journal.document_no, reversed=False
                )
            )
            ve_rows = list(
                ValueEntry.objects.filter(
                    document_no=self.journal.document_no, reversed=False
                )
            )
            if not gl_rows and not ile_rows and not ve_rows:
                raise ValueError(
                    f"No unreversed ledger rows for document {self.journal.document_no}."
                )
            for row in gl_rows + ile_rows + ve_rows:
                row.reversed = True
                row.reversed_by_document_no = self.reversal_document_no
                row.reversed_date = self.reversal_date
                row.reversed_by_user = self.user
                row.save(
                    update_fields=[
                        "reversed",
                        "reversed_by_document_no",
                        "reversed_date",
                        "reversed_by_user",
                    ]
                )
            self._restore_fifo()
            return {
                "mode": "mark_only",
                "reversal_document_no": self.reversal_document_no,
                "marked_gl": len(gl_rows),
                "marked_item_ledger": len(ile_rows),
                "marked_value_entries": len(ve_rows),
            }

        created_gl = []
        for original in gl_rows:
            rev = GeneralLedgerEntry.objects.create(
                posting_date=self.reversal_date,
                document_type=original.document_type,
                document_no=self.reversal_document_no,
                gl_account=original.gl_account,
                description=f"Reversal of {original.document_no}",
                amount=-original.amount,
                receipt_no=original.receipt_no,
                balancing_account_type=original.balancing_account_type,
                general_posting_type=original.general_posting_type,
                general_business_posting_group=original.general_business_posting_group,
                general_product_posting_group=original.general_product_posting_group,
                dimension_set=original.dimension_set,
                global_dimension_1=original.global_dimension_1,
                global_dimension_2=original.global_dimension_2,
                transaction_no=self.transaction_no,
                reverses_entry_no=original.id,
                user=self.user,
            )
            original.reversed = True
            original.reversed_by_document_no = self.reversal_document_no
            original.reversed_date = self.reversal_date
            original.reversed_by_user = self.user
            original.save(
                update_fields=[
                    "reversed",
                    "reversed_by_document_no",
                    "reversed_date",
                    "reversed_by_user",
                ]
            )
            created_gl.append(rev.id)

        created_ile = []
        ile_map: dict[int, ItemLedgerEntries] = {}
        consolidate_inv = self._use_consolidated_inventory_reversal(ile_rows)

        if consolidate_inv:
            template = ile_rows[0]
            base_qty = self._journal_base_quantity()
            rev_qty = base_qty
            rev_total = float(self.journal.amount or 0)
            rev = ItemLedgerEntries.objects.create(
                posting_date=self.reversal_date,
                date=self.reversal_date,
                entry_type=template.entry_type,
                document_type=template.document_type,
                document_no=self.reversal_document_no,
                item=template.item,
                description=f"Reversal of {self.journal.document_no}",
                quantity=rev_qty,
                remaining_quantity=rev_qty,
                total=rev_total,
                unit_of_measure=template.unit_of_measure,
                unit_of_measure_code=template.unit_of_measure_code,
                quantity_per_unit_of_measure=template.quantity_per_unit_of_measure,
                location=template.location,
                lot_no=template.lot_no,
                expiry_date=template.expiry_date,
                serial_no=template.serial_no,
                global_dimension_1=template.global_dimension_1,
                global_dimension_2=template.global_dimension_2,
                dimension_set=template.dimension_set,
                transaction_no=self.transaction_no,
                reverses_entry_no=template.id,
                user=self.user,
            )
            created_ile.append(rev.id)
            for original in ile_rows:
                ile_map[original.id] = rev
                original.reversed = True
                original.reversed_by_document_no = self.reversal_document_no
                original.reversed_date = self.reversal_date
                original.reversed_by_user = self.user
                original.save(
                    update_fields=[
                        "reversed",
                        "reversed_by_document_no",
                        "reversed_date",
                        "reversed_by_user",
                    ]
                )
        else:
            for original in ile_rows:
                rev_qty = -int(original.quantity)
                rev_rem = abs(rev_qty) if rev_qty > 0 else 0
                rev = ItemLedgerEntries.objects.create(
                    posting_date=self.reversal_date,
                    date=self.reversal_date,
                    entry_type=original.entry_type,
                    document_type=original.document_type,
                    document_no=self.reversal_document_no,
                    item=original.item,
                    description=f"Reversal of {original.document_no}",
                    quantity=rev_qty,
                    remaining_quantity=rev_rem,
                    total=-(original.total or 0),
                    unit_of_measure=original.unit_of_measure,
                    unit_of_measure_code=original.unit_of_measure_code,
                    quantity_per_unit_of_measure=original.quantity_per_unit_of_measure,
                    location=original.location,
                    lot_no=original.lot_no,
                    expiry_date=original.expiry_date,
                    serial_no=original.serial_no,
                    global_dimension_1=original.global_dimension_1,
                    global_dimension_2=original.global_dimension_2,
                    dimension_set=original.dimension_set,
                    transaction_no=self.transaction_no,
                    reverses_entry_no=original.id,
                    user=self.user,
                )
                original.reversed = True
                original.reversed_by_document_no = self.reversal_document_no
                original.reversed_date = self.reversal_date
                original.reversed_by_user = self.user
                original.save(
                    update_fields=[
                        "reversed",
                        "reversed_by_document_no",
                        "reversed_date",
                        "reversed_by_user",
                    ]
                )
                ile_map[original.id] = rev
                created_ile.append(rev.id)

        created_ve = []
        if consolidate_inv and ve_rows:
            template_ve = ve_rows[0]
            orig_ile = template_ve.item_ledger_entry_no
            rev_ile = (
                ile_map.get(orig_ile.id) if orig_ile else next(iter(ile_map.values()), None)
            )
            from items.value_entry_posting import bc_normalize_value_entry_fields

            ve_signs = bc_normalize_value_entry_fields(
                EntryType.PositiveAdjustment.name,
                self._journal_base_quantity(),
                float(self.journal.amount or 0),
                cost_per_unit=template_ve.cost_per_unit,
            )
            rev = ValueEntry.objects.create(
                posting_date=self.reversal_date,
                document_no=self.reversal_document_no,
                item=template_ve.item,
                entry_type=EntryType.PositiveAdjustment.name,
                document_type=template_ve.document_type,
                description=f"Reversal of {self.journal.document_no}",
                cost_amount=ve_signs["cost_amount"],
                sales_amount=template_ve.sales_amount,
                cost_per_unit=ve_signs["cost_per_unit"],
                item_ledger_entry_quantity=ve_signs["item_ledger_entry_quantity"],
                invoiced_quantity=ve_signs["invoiced_quantity"],
                valued_quantity=ve_signs["valued_quantity"],
                general_product_posting_group=template_ve.general_product_posting_group,
                inventory_posting_group=template_ve.inventory_posting_group,
                transaction_no=self.transaction_no,
                item_ledger_entry_no=rev_ile,
                location_code=template_ve.location_code,
                global_dimension_1=template_ve.global_dimension_1,
                global_dimension_2=template_ve.global_dimension_2,
                dimension_set=template_ve.dimension_set,
                reverses_value_entry_no=template_ve.id,
            )
            created_ve.append(rev.id)
            for original in ve_rows:
                original.reversed = True
                original.reversed_by_document_no = self.reversal_document_no
                original.reversed_date = self.reversal_date
                original.reversed_by_user = self.user
                original.save(
                    update_fields=[
                        "reversed",
                        "reversed_by_document_no",
                        "reversed_date",
                        "reversed_by_user",
                    ]
                )
        else:
            for original in ve_rows:
                orig_ile = original.item_ledger_entry_no
                rev_ile = ile_map.get(orig_ile.id) if orig_ile else None
                ve_signs = self._reversal_value_entry_signs(original)
                rev = ValueEntry.objects.create(
                    posting_date=self.reversal_date,
                    document_no=self.reversal_document_no,
                    item=original.item,
                    entry_type=ve_signs["entry_type"],
                    document_type=original.document_type,
                    description=f"Reversal of {original.document_no}",
                    cost_amount=ve_signs["cost_amount"],
                    sales_amount=original.sales_amount,
                    cost_per_unit=ve_signs["cost_per_unit"],
                    item_ledger_entry_quantity=ve_signs["item_ledger_entry_quantity"],
                    invoiced_quantity=ve_signs["invoiced_quantity"],
                    valued_quantity=ve_signs["valued_quantity"],
                    general_product_posting_group=original.general_product_posting_group,
                    inventory_posting_group=original.inventory_posting_group,
                    transaction_no=self.transaction_no,
                    item_ledger_entry_no=rev_ile or orig_ile,
                    location_code=original.location_code,
                    global_dimension_1=original.global_dimension_1,
                    global_dimension_2=original.global_dimension_2,
                    dimension_set=original.dimension_set,
                    reverses_value_entry_no=original.id,
                )
                original.reversed = True
                original.reversed_by_document_no = self.reversal_document_no
                original.reversed_date = self.reversal_date
                original.reversed_by_user = self.user
                original.save(
                    update_fields=[
                        "reversed",
                        "reversed_by_document_no",
                        "reversed_date",
                        "reversed_by_user",
                    ]
                )
                created_ve.append(rev.id)

        # Reversing item ledger lines restore on-hand; FIFO bump only for mark-only.
        if not created_ile:
            self._restore_fifo()

        return {
            "mode": "create_reversing_entries",
            "reversal_document_no": self.reversal_document_no,
            "transaction_no": self.transaction_no,
            "created_gl": created_gl,
            "created_item_ledger": created_ile,
            "created_value_entries": created_ve,
        }

    def _restore_fifo(self) -> None:
        if self.journal.entry_type != EntryType.NegativeAdjustment.name:
            return

        specs = (
            TrackingSpecification.objects.filter(item_journal=self.journal)
            .exclude(lot_no__isnull=True)
            .exclude(lot_no="")
            .order_by("-id")
        )
        if specs.exists():
            for spec in specs:
                qty = int(spec.quantity_base or 0)
                if qty <= 0:
                    continue
                lot_no = (spec.lot_no or "").strip()
                entries = ItemLedgerEntries.objects.filter(
                    item=self.journal.item,
                    lot_no=lot_no,
                    remaining_quantity__gte=0,
                )
                if self.journal.location_code_id:
                    entries = entries.filter(location_id=self.journal.location_code_id)
                if self.journal.global_dimension_1_id:
                    entries = entries.filter(
                        global_dimension_1_id=self.journal.global_dimension_1_id
                    )
                entries = entries.order_by("-expiry_date", "-created_at")
                remaining = qty
                for entry in entries:
                    if remaining <= 0:
                        break
                    entry.remaining_quantity += remaining
                    entry.save(update_fields=["remaining_quantity", "updated_at"])
                    remaining = 0
            return

        try:
            uom = ItemUnitOfMeasure.objects.get(
                id=self.journal.item_unit_of_measure_id
            )
            qty = int(uom.quantity_per_unit) * int(self.journal.quantity or 0)
        except ItemUnitOfMeasure.DoesNotExist:
            qty = int(self.journal.quantity or 0)
        if qty <= 0:
            return

        entries = ItemLedgerEntries.objects.filter(
            item=self.journal.item,
            remaining_quantity__gte=0,
        ).order_by("-created_at")
        if self.journal.location_code_id:
            entries = entries.filter(location_id=self.journal.location_code_id)
        if self.journal.global_dimension_1_id:
            entries = entries.filter(
                global_dimension_1_id=self.journal.global_dimension_1_id
            )

        remaining = qty
        for entry in entries:
            if remaining <= 0:
                break
            entry.remaining_quantity += remaining
            entry.save(update_fields=["remaining_quantity", "updated_at"])
            remaining = 0


def clone_item_journal_from_source(
    *,
    source: ItemJournal,
    user,
) -> ItemJournal:
    """Create an open journal line copying source fields and tracking specs."""
    from common.enums import Status

    clone = ItemJournal(
        item=source.item,
        journal_template=source.journal_template,
        journal_batch=source.journal_batch,
        entry_type=source.entry_type,
        type=source.type,
        description=source.description,
        quantity=source.quantity,
        physical_quantity=source.physical_quantity,
        calculated_quantity=source.calculated_quantity,
        item_unit_of_measure=source.item_unit_of_measure,
        unit_amount=source.unit_amount,
        amount=source.amount,
        unit_cost=source.unit_cost,
        location_code=source.location_code,
        date=source.date,
        user=user,
        global_dimension_1=source.global_dimension_1,
        dimension_set=source.dimension_set,
        status=Status.Open.value,
    )
    clone.save()

    for spec in TrackingSpecification.objects.filter(item_journal=source).order_by(
        "id"
    ):
        TrackingSpecification.objects.create(
            item=spec.item,
            location_code=spec.location_code,
            serial_no=spec.serial_no,
            lot_no=spec.lot_no,
            expiry_date=spec.expiry_date,
            quantity_base=spec.quantity_base,
            item_journal=clone,
            source_template=spec.source_template or source.journal_template,
            source_batch=spec.source_batch or source.journal_batch,
        )

    return clone
