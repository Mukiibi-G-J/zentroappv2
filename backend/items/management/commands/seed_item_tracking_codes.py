from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from items.models import ItemTrackingCodes


# System defaults cloned into every new company via `_zentro_template`.
# "ALL LOT" is protected from delete on the model.
DEFAULT_TRACKING_CODES = (
    {
        "code": "ALL LOT",
        "description": "Lot No. + Expiry Date required",
        "require_serial_no": False,
        "require_lot_no": True,
        "require_expiry_date": True,
    },
    {
        "code": "LOTALL",
        "description": "Lot No. required",
        "require_serial_no": False,
        "require_lot_no": True,
        "require_expiry_date": False,
    },
    {
        "code": "SERIAL",
        "description": "Serial No. required",
        "require_serial_no": True,
        "require_lot_no": False,
        "require_expiry_date": False,
    },
)


class Command(BaseCommand):
    help = "Seed default Item Tracking Codes (ALL LOT, LOTALL, SERIAL)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            metavar="SCHEMA",
            help="Only this schema_name. If omitted, all tenant companies (excl. public).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete non-system tracking codes before seeding (keeps ALL LOT).",
        )

    def _seed_schema(self, schema_name: str, *, clear: bool) -> None:
        with schema_context(schema_name):
            if clear:
                deleted, _ = (
                    ItemTrackingCodes.objects.exclude(code="ALL LOT").delete()
                )
                self.stdout.write(f"  {schema_name}: cleared {deleted} code(s)")

            created = 0
            updated = 0
            for spec in DEFAULT_TRACKING_CODES:
                _, was_created = ItemTrackingCodes.objects.update_or_create(
                    code=spec["code"],
                    defaults={
                        "description": spec["description"],
                        "require_serial_no": spec["require_serial_no"],
                        "require_lot_no": spec["require_lot_no"],
                        "require_expiry_date": spec["require_expiry_date"],
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {schema_name}: tracking codes created={created} updated={updated}"
                )
            )

    def handle(self, *args, **options):
        clear = options.get("clear", False)
        tenant = options.get("tenant")

        self.stdout.write("Seeding Item Tracking Codes...")

        if tenant:
            self._seed_schema(tenant, clear=clear)
            return

        TenantModel = get_tenant_model()
        for company in TenantModel.objects.exclude(schema_name="public"):
            self._seed_schema(company.schema_name, clear=clear)

        self.stdout.write(self.style.SUCCESS("Done seeding Item Tracking Codes."))
