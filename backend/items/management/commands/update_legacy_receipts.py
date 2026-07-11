from django.core.management.base import BaseCommand
from items.models import ItemLedgerEntries
from django_tenants.utils import get_tenant_model
import uuid


class Command(BaseCommand):
    help = "Updates all existing ItemLedgerEntries with a legacy receipt number for all tenants"

    def handle(self, *args, **kwargs):
        # Get all tenants
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name="public")

        for tenant in tenants:
            # Activate tenant's schema
            tenant.activate()

            default_receipt_no = f"RCP-LEGACY-{uuid.uuid4().hex[:6].upper()}"

            updated = ItemLedgerEntries.objects.filter(receipt_no__isnull=True).update(
                receipt_no=default_receipt_no
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Tenant: {tenant.schema_name} - Updated {updated} entries with receipt number: {default_receipt_no}"
                )
            )
