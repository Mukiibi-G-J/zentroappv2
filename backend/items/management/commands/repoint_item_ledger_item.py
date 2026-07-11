"""
Repoint inventory and related records from one item number to another (same tenant schema).

Primary: ItemLedgerEntries + ValueEntry (always all ValueEntry rows with the source item).
Also: PhysInventoryLedgerEntry, sales lines, TrackingSpecification, ItemJournal; scoped by
one warehouse: --location-code, --location-icontains, or --location-id (see command help).

Dry-run by default; pass --apply to commit.

Example:
  python manage.py repoint_item_ledger_item \\
    --schema=your_tenant \\
    --from-item-no=ITM-000829 \\
    --to-item-no=ITM-000145 \\
    --location-icontains=Mwanjari \\
    --apply
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.db.utils import ProgrammingError
from django_tenants.utils import schema_context

from common.enums import Status
from items.enums import EntryType
from items.models import (
    Item,
    ItemJournal,
    ItemLedgerEntries,
    ItemUnitOfMeasure,
    Location,
    PhysInventoryLedgerEntry,
    TrackingSpecification,
    ValueEntry,
)
from sales.models import (
    PostedSalesInvoice,
    PostedSalesInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)

_SALES_ENTRY_TYPES = (EntryType.Sales.name, EntryType.Sales.value)


def _item_journal_sales_scoped_qs(
    from_item: Item,
    *,
    location_pk: int,
    sales_doc_nos: list[str],
):
    """Sales ItemJournal rows tied to the same invoice numbers and branch (Open or Posted)."""
    return ItemJournal.objects.filter(
        item=from_item,
        location_code_id=location_pk,
        document_no__in=sales_doc_nos,
        entry_type__in=_SALES_ENTRY_TYPES,
        status__in=(Status.Open.value, Status.Posted.value),
    )


def _posted_sales_invoice_for_sales_invoice(si: SalesInvoice) -> PostedSalesInvoice | None:
    """
    PostedSalesInvoice.no is generated from the posted-invoice number series and is usually
    NOT the same as SalesInvoice.invoice_no (which ItemLedgerEntries.document_no uses).
    Match the same way as sales/views.py reversal flow.
    """
    if si.customer_invoice_no:
        posted = PostedSalesInvoice.objects.filter(
            customer_invoice_no=si.customer_invoice_no,
            customer_id=si.customer_id,
        ).first()
        if posted:
            return posted
    return (
        PostedSalesInvoice.objects.filter(
            customer_id=si.customer_id,
            document_date=si.document_date,
        )
        .order_by("-id")
        .first()
    )


def _posted_sales_line_pks_for_ledger_sales_docs(
    sales_doc_nos: list[str],
    from_item: Item,
    *,
    location_pk: int,
) -> list[int]:
    """
    Return PKs of PostedSalesInvoiceLine rows for sales ILE document_no values.

    Resolves SalesInvoice by invoice_no, then PostedSalesInvoice by customer_invoice_no
    (or customer + document_date fallback). Also includes any line where posted header
    ``no`` equals the ledger doc no (legacy / alternate setups).

    ``location_pk`` is ``Location`` primary key (``location_code_id`` on lines).
    """
    pks: list[int] = []
    loc_q = Q(location_code_id=location_pk) | Q(location_code_id__isnull=True)

    for doc_no in sales_doc_nos:
        si = SalesInvoice.objects.filter(invoice_no=doc_no).first()
        if si:
            posted = _posted_sales_invoice_for_sales_invoice(si)
            if posted:
                qs = PostedSalesInvoiceLine.objects.filter(
                    posted_sales_invoice=posted,
                    item=from_item,
                ).filter(loc_q)
                pks.extend(qs.values_list("pk", flat=True))

    legacy = PostedSalesInvoiceLine.objects.filter(
        posted_sales_invoice__no__in=sales_doc_nos,
        item=from_item,
    ).filter(loc_q)
    pks.extend(legacy.values_list("pk", flat=True))

    return list(dict.fromkeys(pks))


def _location_table_exists() -> bool:
    """True if Location is migrated in the current DB schema."""
    table = Location._meta.db_table
    with connection.cursor() as cursor:
        names = connection.introspection.table_names(cursor)
    return table in names


@dataclass(frozen=True)
class LocationScope:
    """Resolved warehouse scope: always a PK; optional code when Location row is readable."""

    pk: int
    code: str | None = None

    def label(self) -> str:
        if self.code:
            return f"{self.code!r} (id={self.pk})"
        return f"id={self.pk} (no Location row readable in this schema)"


def _distinct_ile_location_ids(from_item: Item, *, limit: int = 40) -> list[int]:
    """FK targets on ItemLedgerEntries.location_id for this item (no Location table needed)."""
    qs = (
        ItemLedgerEntries.objects.filter(item=from_item)
        .exclude(location_id__isnull=True)
        .values_list("location_id", flat=True)
        .distinct()
        .order_by("location_id")
    )
    return list(qs[:limit])


def _resolve_location_scope(
    from_item: Item,
    *,
    location_code: str | None,
    location_icontains: str | None,
    location_id: int | None,
) -> LocationScope:
    """
    Resolve scope inside tenant schema_context.

    ``--location-id`` works even when ``items_location`` is missing, as long as
    ``ItemLedgerEntries`` rows reference that ``location_id``.
    """
    if location_id is not None:
        if not ItemLedgerEntries.objects.filter(
            item=from_item, location_id=location_id
        ).exists():
            sample = _distinct_ile_location_ids(from_item)
            raise CommandError(
                f"No ItemLedgerEntries for the source item use location_id={location_id}. "
                f"Distinct location_id values on this item's ledger (sample): "
                f"{sample if sample else '(none or all null)'}"
            )
        code: str | None = None
        if _location_table_exists():
            try:
                loc = Location.objects.filter(pk=location_id).first()
                if loc:
                    code = loc.code
            except ProgrammingError:
                pass
        return LocationScope(pk=location_id, code=code)

    if location_code and location_icontains:
        raise CommandError("Pass only one of --location-code or --location-icontains.")
    if not location_code and not location_icontains:
        raise CommandError(
            "Location scope is required: pass one of --location-code, --location-icontains, "
            "or --location-id."
        )
    if not _location_table_exists():
        sample = _distinct_ile_location_ids(from_item)
        raise CommandError(
            f"Location table {Location._meta.db_table!r} is missing in this tenant schema "
            "(migrations not applied on this company). You cannot use --location-code or "
            "--location-icontains without that table. Either run tenant migrations for the "
            "items app, or scope by primary key with --location-id using a value from "
            f"ItemLedgerEntries.location_id for this item, for example: {sample}"
        )
    try:
        if location_code:
            loc = Location.objects.filter(code__iexact=location_code.strip()).first()
            if not loc:
                raise CommandError(f"No Location with code matching {location_code!r}.")
            return LocationScope(pk=loc.pk, code=loc.code)
        term = location_icontains.strip()
        qs = Location.objects.filter(
            Q(code__icontains=term) | Q(description__icontains=term)
        )
        n = qs.count()
        if n == 0:
            raise CommandError(
                f"No Location matching icontains={location_icontains!r} on code or description."
            )
        if n > 1:
            codes = list(qs.values_list("code", flat=True)[:20])
            raise CommandError(
                f"Multiple locations ({n}) match {location_icontains!r}; "
                f"use --location-code or --location-id. Sample codes: {codes}"
            )
        loc = qs.first()
        assert loc is not None
        return LocationScope(pk=loc.pk, code=loc.code)
    except ProgrammingError as e:
        raise CommandError(
            f"Could not read Location table in this schema ({e}). "
            "Fix tenant migrations or use --location-id."
        ) from e


def _phys_inventory_table_exists() -> bool:
    """True if PhysInventoryLedgerEntry is migrated in the current DB schema."""
    table = PhysInventoryLedgerEntry._meta.db_table
    with connection.cursor() as cursor:
        names = connection.introspection.table_names(cursor)
    return table in names


def _resolve_dest_line_uoms(to_item: Item, line_uom_id: int | None):
    """Return (item_unit_of_measure, unit_of_measure) for destination item."""
    if line_uom_id:
        iuom = ItemUnitOfMeasure.objects.filter(
            item=to_item, unit_of_measure_id=line_uom_id
        ).first()
        if iuom:
            return iuom, iuom.unit_of_measure
    iuom = ItemUnitOfMeasure.objects.filter(item=to_item, default=True).first()
    if not iuom:
        iuom = ItemUnitOfMeasure.objects.filter(item=to_item).first()
    if not iuom:
        raise CommandError(
            f"Destination item {to_item.no!r} has no ItemUnitOfMeasure; cannot remap sales lines."
        )
    return iuom, iuom.unit_of_measure


class Command(BaseCommand):
    help = (
        "Repoint ItemLedgerEntries (+ ValueEntry, phys inventory, sales lines, tracking, "
        "item journals) from one item to another for one warehouse/location.\n"
        "Pass exactly one of: --location-code, --location-icontains, or --location-id "
        "(warehouse PK from ItemLedgerEntries.location_id when items_location is missing).\n\n"
        "Without --apply: dry-run only (counts, sample ledger rows, no DB writes).\n"
        "Per-tenant: pass your company schema name from django-tenants (repeat per schema if needed).\n\n"
        "Examples:\n"
        "  python manage.py repoint_item_ledger_item --schema=YOUR_TENANT "
        "--from-item-no=ITM-000829 --to-item-no=ITM-000145 --location-icontains=Mwanjari\n"
        "  python manage.py repoint_item_ledger_item --schema=YOUR_TENANT "
        "--from-item-no=ITM-000829 --to-item-no=ITM-000145 --location-code=MWANJARI --apply\n"
        "  python manage.py repoint_item_ledger_item --schema=YOUR_TENANT "
        "--from-item-no=ITM-000829 --to-item-no=ITM-000145 --location-id=3 --apply"
    )

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            required=True,
            help="Tenant schema name (e.g. hardwareworld)",
        )
        parser.add_argument(
            "--from-item-no",
            required=True,
            help="Wrong item no. (e.g. ITM-000829)",
        )
        parser.add_argument(
            "--to-item-no",
            required=True,
            help="Correct item no. (e.g. ITM-000145)",
        )
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument(
            "--location-code",
            dest="location_code",
            help="Exact location code (case-insensitive match).",
        )
        g.add_argument(
            "--location-icontains",
            dest="location_icontains",
            help="Single location: match code or description icontains this string.",
        )
        g.add_argument(
            "--location-id",
            dest="location_id",
            type=int,
            help=(
                "Warehouse PK (ItemLedgerEntries.location_id / sales line location_code_id). "
                "Use when items_location is not migrated: pick an id that appears on the "
                "source item's ledger rows (command error text lists samples when relevant)."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform updates (default is dry-run only).",
        )
        parser.add_argument(
            "--skip-phys-inventory",
            action="store_true",
            help="Do not update PhysInventoryLedgerEntry rows.",
        )
        parser.add_argument(
            "--skip-sales-lines",
            action="store_true",
            help=(
                "Do not update posted/open sales invoice lines, sales-scoped ItemJournal "
                "(Open/Posted), or related TrackingSpecification rows."
            ),
        )

    def handle(self, *args, **options):
        schema = options["schema"]
        from_no = options["from_item_no"].strip()
        to_no = options["to_item_no"].strip()
        apply = options["apply"]
        skip_phys = options["skip_phys_inventory"]
        skip_sales = options["skip_sales_lines"]
        loc_code = options.get("location_code")
        loc_ic = options.get("location_icontains")
        loc_id = options.get("location_id")

        with schema_context(schema):
            self._run(
                schema=schema,
                from_no=from_no,
                to_no=to_no,
                apply=apply,
                skip_phys=skip_phys,
                skip_sales=skip_sales,
                location_code=loc_code,
                location_icontains=loc_ic,
                location_id=loc_id,
            )

    def _run(
        self,
        *,
        schema: str,
        from_no: str,
        to_no: str,
        apply: bool,
        skip_phys: bool,
        skip_sales: bool,
        location_code: str | None,
        location_icontains: str | None,
        location_id: int | None,
    ):
        if from_no == to_no:
            raise CommandError("--from-item-no and --to-item-no must differ.")

        try:
            from_item = Item.objects.get(no=from_no)
        except Item.DoesNotExist as e:
            raise CommandError(f"Source item {from_no!r} not found.") from e
        try:
            to_item = Item.objects.get(no=to_no)
        except Item.DoesNotExist as e:
            raise CommandError(f"Destination item {to_no!r} not found.") from e

        scope = _resolve_location_scope(
            from_item,
            location_code=location_code,
            location_icontains=location_icontains,
            location_id=location_id,
        )

        ile_qs = ItemLedgerEntries.objects.filter(item=from_item, location_id=scope.pk)
        ile_count = ile_qs.count()
        pk_list = list(ile_qs.values_list("pk", flat=True))

        ve_all_count = ValueEntry.objects.filter(item=from_item).count()
        from_item_iuom_ids = list(
            ItemUnitOfMeasure.objects.filter(item=from_item).values_list("pk", flat=True)
        )
        journal_stale_q = Q(item=from_item)
        if from_item_iuom_ids:
            journal_stale_q |= Q(item_unit_of_measure_id__in=from_item_iuom_ids)
        journal_stale_count = ItemJournal.objects.filter(journal_stale_q).distinct().count()
        ts_item_count = TrackingSpecification.objects.filter(item=from_item).count()
        open_line_all = 0
        posted_line_all = 0
        if not skip_sales:
            open_line_all = SalesInvoiceLine.objects.filter(
                item=from_item, location_code_id=scope.pk
            ).count()
            posted_line_all = PostedSalesInvoiceLine.objects.filter(
                item=from_item, location_code_id=scope.pk
            ).count()

        self.stdout.write(
            self.style.NOTICE(
                f"Tenant schema: {schema!r} | Location: {scope.label()}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"ItemLedgerEntries (inventory ledger): {ile_count} row(s) "
                f"from item {from_no!r} -> {to_no!r}"
            )
        )

        if (
            ile_count == 0
            and ve_all_count == 0
            and journal_stale_count == 0
            and ts_item_count == 0
            and (skip_sales or (open_line_all == 0 and posted_line_all == 0))
        ):
            phys_only = False
            if _phys_inventory_table_exists():
                try:
                    phys_only = PhysInventoryLedgerEntry.objects.filter(
                        item=from_item
                    ).exists()
                except ProgrammingError:
                    phys_only = False
            if not phys_only:
                self.stdout.write(
                    self.style.WARNING(
                        "Nothing to do (no ItemLedgerEntries, ValueEntry, journals, tracking, "
                        "or sales lines for the source item at this location / in scope)."
                    )
                )
                return

        ile_doc_nos = list(ile_qs.values_list("document_no", flat=True).distinct())

        self.stdout.write(
            f"ValueEntry (all rows with item={from_no!r}): {ve_all_count} - "
            f"with --apply every such row is set to item={to_no!r} (costing alignment)."
        )
        self.stdout.write(
            f"ItemJournal rows (still on source item or its unit-of-measure rows): "
            f"{journal_stale_count}"
        )
        self.stdout.write(
            f"TrackingSpecification rows (item={from_no!r}): {ts_item_count} - "
            "with --apply, every such row is set to the destination item (including specs "
            "on adjustment ItemJournals ITMJ-*), so the source item can be deleted."
        )

        phys_filter = Q(item=from_item)
        if pk_list:
            phys_filter |= Q(item_ledger_entry_id__in=pk_list)

        phys_table_ok = False
        if not skip_phys:
            phys_table_ok = _phys_inventory_table_exists()
            if not phys_table_ok:
                self.stdout.write(
                    self.style.WARNING(
                        f"PhysInventoryLedgerEntry: table "
                        f"{PhysInventoryLedgerEntry._meta.db_table!r} missing in this schema; "
                        f"skipping phys rows (migrate tenant if you need phys audit updates)."
                    )
                )
        phys_count = 0
        if phys_table_ok:
            try:
                phys_count = PhysInventoryLedgerEntry.objects.filter(phys_filter).count()
            except ProgrammingError:
                phys_table_ok = False
                phys_count = 0
                self.stdout.write(
                    self.style.WARNING(
                        "PhysInventoryLedgerEntry: query failed; skipping phys rows."
                    )
                )

        sales_entry_type = EntryType.Sales.name
        sales_doc_nos = list(
            ile_qs.filter(entry_type=sales_entry_type)
            .values_list("document_no", flat=True)
            .distinct()
        )
        posted_sales_count = 0
        open_sales_count = 0
        ts_count = 0
        posted_line_pks: list[int] = []
        journal_sales_open = 0
        journal_sales_posted = 0
        ts_journal_count = 0
        sales_journal_pks: list[int] = []
        if not skip_sales:
            if sales_doc_nos:
                posted_line_pks = _posted_sales_line_pks_for_ledger_sales_docs(
                    sales_doc_nos, from_item, location_pk=scope.pk
                )
                posted_sales_count = len(posted_line_pks)
                open_sales_count = SalesInvoiceLine.objects.filter(
                    sales_invoice__invoice_no__in=sales_doc_nos,
                    item_id=from_no,
                    location_code_id=scope.pk,
                ).count()
                open_line_ids = list(
                    SalesInvoiceLine.objects.filter(
                        sales_invoice__invoice_no__in=sales_doc_nos,
                        item_id=from_no,
                        location_code_id=scope.pk,
                    ).values_list("pk", flat=True)
                )
                ts_count = (
                    TrackingSpecification.objects.filter(
                        sales_invoice_line_id__in=open_line_ids
                    ).count()
                    if open_line_ids
                    else 0
                )
                ij_sales = _item_journal_sales_scoped_qs(
                    from_item,
                    location_pk=scope.pk,
                    sales_doc_nos=sales_doc_nos,
                )
                journal_sales_open = ij_sales.filter(status=Status.Open.value).count()
                journal_sales_posted = ij_sales.filter(status=Status.Posted.value).count()
                sales_journal_pks = list(ij_sales.values_list("pk", flat=True))
                ts_journal_count = (
                    TrackingSpecification.objects.filter(
                        item_journal_id__in=sales_journal_pks,
                        item=from_item,
                    ).count()
                    if sales_journal_pks
                    else 0
                )

        if skip_phys:
            self.stdout.write("PhysInventoryLedgerEntry: skipped (--skip-phys-inventory)")
        elif phys_table_ok:
            self.stdout.write(f"PhysInventoryLedgerEntry rows (scoped): {phys_count}")
        if skip_sales:
            self.stdout.write(
                "Sales lines / TrackingSpecification (invoice lines) / "
                "sales ItemJournal (Open+Posted): skipped"
            )
        else:
            self.stdout.write(
                f"Sales document_no (Sales-type ILE): {sales_doc_nos[:30]}"
                + (" ..." if len(sales_doc_nos) > 30 else "")
            )
            self.stdout.write(
                f"PostedSalesInvoiceLine (resolved): {posted_sales_count}, "
                f"SalesInvoiceLine (open, in scope): {open_sales_count}, "
                f"TrackingSpecification (linked to those open lines only): {ts_count}"
            )
            if sales_doc_nos:
                self.stdout.write(
                    f"ItemJournal (Sales, same document_no + branch, Open): {journal_sales_open}, "
                    f"Posted: {journal_sales_posted}; "
                    f"TrackingSpecification (on those journals): {ts_journal_count}"
                )
            if sales_doc_nos and ts_count == 0 and ts_item_count > 0:
                self.stdout.write(
                    "Note: TrackingSpecification rows exist for this item (total above) but "
                    "not on open invoice lines matching these Sales-type ILE document_no values "
                    "and location - e.g. already posted, journals/purchases only, or lines "
                    "without tracking lines."
                )
            if sales_doc_nos:
                self.stdout.write(
                    "Note: item ledger document_no is SalesInvoice.invoice_no (e.g. SIN-...); "
                    "PostedSalesInvoice.no is usually a different posted-series number - "
                    "posted lines are matched via SalesInvoice -> PostedSalesInvoice "
                    "(customer_invoice_no + customer, same as sales reversal)."
                )

        if ile_count:
            sample = list(
                ile_qs.values(
                    "id", "document_no", "entry_type", "quantity", "remaining_quantity"
                )[:15]
            )
            self.stdout.write("Sample ItemLedgerEntries (up to 15):")
            for row in sample:
                self.stdout.write(
                    f"  id={row['id']} doc={row['document_no']!r} "
                    f"type={row['entry_type']!r} qty={row['quantity']} "
                    f"rem={row['remaining_quantity']}"
                )
        else:
            self.stdout.write("Sample ItemLedgerEntries: (none in scope)")

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only. Re-run with --apply to commit "
                    "(single transaction: ledger, value entries, phys, sales, tracking, journals)."
                )
            )
            return

        with transaction.atomic():
            n_var = 0
            n_ile = 0
            if pk_list:
                n_var = (
                    ItemLedgerEntries.objects.filter(pk__in=pk_list)
                    .exclude(variant_id__isnull=True)
                    .exclude(variant__item_id=to_no)
                    .update(variant_id=None)
                )
                n_ile = ItemLedgerEntries.objects.filter(pk__in=pk_list).update(item=to_item)
            n_ve = ValueEntry.objects.filter(item=from_item).update(item=to_item)
            n_phys = 0
            if phys_table_ok:
                try:
                    desc = to_item.item_name or ""
                    n_phys = PhysInventoryLedgerEntry.objects.filter(phys_filter).update(
                        item=to_item, item_no=to_no, description=desc
                    )
                except ProgrammingError:
                    self.stdout.write(
                        self.style.WARNING(
                            "PhysInventoryLedgerEntry: update skipped (table missing)."
                        )
                    )

            n_posted = 0
            n_open = 0
            n_ts = 0
            n_ts_journal = 0
            n_journal_sales = 0
            n_journal_other = 0
            if not skip_sales and sales_doc_nos:
                posted_lines = list(
                    PostedSalesInvoiceLine.objects.filter(
                        pk__in=posted_line_pks,
                    ).select_related("unit_of_measure")
                )
                for line in posted_lines:
                    iuom, uom = _resolve_dest_line_uoms(
                        to_item,
                        line.unit_of_measure_id if line.unit_of_measure_id else None,
                    )
                    PostedSalesInvoiceLine.objects.filter(pk=line.pk).update(
                        item_id=to_no,
                        item_unit_of_measure=iuom,
                        unit_of_measure=uom,
                    )
                    n_posted += 1

                open_lines = list(
                    SalesInvoiceLine.objects.filter(
                        sales_invoice__invoice_no__in=sales_doc_nos,
                        item_id=from_no,
                        location_code_id=scope.pk,
                    ).select_related("unit_of_measure")
                )
                open_ids = []
                for line in open_lines:
                    iuom, uom = _resolve_dest_line_uoms(
                        to_item,
                        line.unit_of_measure_id if line.unit_of_measure_id else None,
                    )
                    SalesInvoiceLine.objects.filter(pk=line.pk).update(
                        item_id=to_no,
                        item_unit_of_measure=iuom,
                        unit_of_measure=uom,
                    )
                    open_ids.append(line.pk)
                    n_open += 1
                if open_ids:
                    n_ts = TrackingSpecification.objects.filter(
                        sales_invoice_line_id__in=open_ids
                    ).update(item=to_item)

                if sales_journal_pks:
                    for j in ItemJournal.objects.filter(pk__in=sales_journal_pks).select_related(
                        "item_unit_of_measure"
                    ):
                        um_id = (
                            j.item_unit_of_measure.unit_of_measure_id
                            if j.item_unit_of_measure_id
                            else None
                        )
                        iuom, _ = _resolve_dest_line_uoms(to_item, um_id)
                        ItemJournal.objects.filter(pk=j.pk).update(
                            item=to_item,
                            item_unit_of_measure=iuom,
                        )
                        n_journal_sales += 1
                    n_ts_journal = TrackingSpecification.objects.filter(
                        item_journal_id__in=sales_journal_pks,
                        item=from_item,
                    ).update(item=to_item)

            rest_q = Q(item=from_item)
            if from_item_iuom_ids:
                rest_q |= Q(item_unit_of_measure_id__in=from_item_iuom_ids)
            rest_journals = ItemJournal.objects.filter(rest_q).distinct()
            if sales_journal_pks:
                rest_journals = rest_journals.exclude(pk__in=sales_journal_pks)
            n_journal_other = 0
            for j in rest_journals.select_related("item_unit_of_measure"):
                um_id = (
                    j.item_unit_of_measure.unit_of_measure_id
                    if j.item_unit_of_measure_id
                    else None
                )
                iuom, _ = _resolve_dest_line_uoms(to_item, um_id)
                ItemJournal.objects.filter(pk=j.pk).update(
                    item=to_item,
                    item_unit_of_measure=iuom,
                )
                n_journal_other += 1

            # Like ValueEntry: any TrackingSpecification still keyed to the source item
            # (e.g. lot/serial on adjustment ItemJournals ITMJ-*) must move or the source
            # Item cannot be deleted even when ItemJournal.item was already updated.
            n_ts_remain = TrackingSpecification.objects.filter(item=from_item).update(
                item=to_item
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Applied: "
                f"ItemLedgerEntries={n_ile}, variant_cleared={n_var}, ValueEntry={n_ve}, "
                f"PhysInventoryLedgerEntry={n_phys}, "
                f"PostedSalesInvoiceLine={n_posted}, SalesInvoiceLine={n_open}, "
                f"TrackingSpecification (invoice lines)={n_ts}, "
                f"TrackingSpecification (sales journals)={n_ts_journal}, "
                f"TrackingSpecification (all other, incl. adjustment journals)={n_ts_remain}, "
                f"ItemJournal sales Open/Posted+UOM={n_journal_sales}, "
                f"ItemJournal other={n_journal_other}."
            )
        )
        ve_left_on_source = ValueEntry.objects.filter(item=from_item).count()
        if ve_left_on_source:
            self.stdout.write(
                self.style.ERROR(
                    f"ValueEntry check failed: {ve_left_on_source} row(s) still point at "
                    f"source item {from_no!r} - investigate."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"ValueEntry check OK: no ValueEntry rows remain on source item {from_no!r}."
                )
            )
        ts_left_on_source = TrackingSpecification.objects.filter(item=from_item).count()
        if ts_left_on_source:
            self.stdout.write(
                self.style.ERROR(
                    f"TrackingSpecification check failed: {ts_left_on_source} row(s) still "
                    f"reference source item {from_no!r} - investigate."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"TrackingSpecification check OK: no tracking rows remain on source item "
                    f"{from_no!r}."
                )
            )
