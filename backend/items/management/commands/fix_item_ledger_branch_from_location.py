"""
Align posted item/value (and optionally G/L) dimensions with Location.code → DimensionValue.

Use when a sales or other posting stamped global_dimension_1 wrong (e.g. CENTRAL) while
location is MWANJARI, so branch-filtered item ledgers hide the row.

Example:
  python manage.py fix_item_ledger_branch_from_location --schema=primewise --document-no=SIN-007739 --fix-gl
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from dimension.models import DimensionValue, get_posting_dimension_payload
from items.models import ItemLedgerEntries, ValueEntry
from financials.models import GeneralLedgerEntry


class Command(BaseCommand):
    help = (
        "Set ItemLedgerEntries (+ ValueEntry, optional G/L) branch dimensions from location.code."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            required=True,
            help="Tenant schema name (e.g. primewise)",
        )
        parser.add_argument(
            "--document-no",
            required=True,
            help="Item ledger document_no (e.g. SIN-007739)",
        )
        parser.add_argument(
            "--fix-gl",
            action="store_true",
            help="Also update GeneralLedgerEntry with the same document_no",
        )

    def handle(self, *args, **options):
        schema = options["schema"]
        document_no = options["document_no"]
        fix_gl = options["fix_gl"]

        with schema_context(schema):
            with transaction.atomic():
                entries = list(
                    ItemLedgerEntries.objects.filter(document_no=document_no)
                    .select_related("location")
                )
                if not entries:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No ItemLedgerEntries for document_no={document_no!r} in schema={schema!r}"
                        )
                    )
                    return

                fixed_ile = 0
                fixed_ve = 0

                for ile in entries:
                    if not ile.location_id:
                        self.stdout.write(
                            self.style.WARNING(
                                f"ILE id={ile.id}: no location; skipped"
                            )
                        )
                        continue

                    loc_code = ile.location.code
                    dv = DimensionValue.objects.filter(code=loc_code).first()
                    if not dv:
                        self.stdout.write(
                            self.style.ERROR(
                                f"ILE id={ile.id}: no DimensionValue for code={loc_code!r}"
                            )
                        )
                        continue

                    payload = get_posting_dimension_payload(
                        global_dimension_1=dv,
                        dimension_set=ile.dimension_set,
                    )
                    g1 = payload.get("global_dimension_1")
                    g2 = payload.get("global_dimension_2")
                    ds = payload.get("dimension_set")
                    if not g1 or not ds:
                        self.stdout.write(
                            self.style.ERROR(
                                f"ILE id={ile.id}: could not build dimension payload"
                            )
                        )
                        continue

                    if (
                        ile.global_dimension_1_id == g1.id
                        and ile.dimension_set_id == ds.id
                        and (g2 is None or ile.global_dimension_2_id == g2.id)
                    ):
                        continue

                    ItemLedgerEntries.objects.filter(pk=ile.pk).update(
                        global_dimension_1_id=g1.id,
                        global_dimension_2_id=g2.id if g2 else None,
                        dimension_set_id=ds.id,
                    )
                    fixed_ile += 1

                    fixed_ve += ValueEntry.objects.filter(
                        item_ledger_entry_no_id=ile.pk
                    ).update(
                        global_dimension_1_id=g1.id,
                        global_dimension_2_id=g2.id if g2 else None,
                        dimension_set_id=ds.id,
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Item ledger rows updated: {fixed_ile}, value entry rows: {fixed_ve}."
                    )
                )

                if fix_gl:
                    ref = (
                        ItemLedgerEntries.objects.filter(
                            document_no=document_no,
                            location_id__isnull=False,
                        )
                        .select_related("location")
                        .first()
                    )
                    if not ref or not ref.location_id:
                        self.stdout.write(
                            self.style.WARNING(
                                "--fix-gl: no ILE with location; skipped G/L update"
                            )
                        )
                    else:
                        dv = DimensionValue.objects.filter(
                            code=ref.location.code
                        ).first()
                        if not dv:
                            self.stdout.write(
                                self.style.ERROR(
                                    "--fix-gl: could not resolve branch dimension"
                                )
                            )
                        else:
                            payload = get_posting_dimension_payload(
                                global_dimension_1=dv,
                                dimension_set=ref.dimension_set,
                            )
                            g1 = payload.get("global_dimension_1")
                            g2 = payload.get("global_dimension_2")
                            ds = payload.get("dimension_set")
                            if g1 and ds:
                                n = GeneralLedgerEntry.objects.filter(
                                    document_no=document_no
                                ).update(
                                    global_dimension_1_id=g1.id,
                                    global_dimension_2_id=g2.id if g2 else None,
                                    dimension_set_id=ds.id,
                                )
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"General ledger rows updated: {n}."
                                    )
                                )
