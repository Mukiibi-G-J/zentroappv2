import json
from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context
from purchases.models import PurchasePayable


class Command(BaseCommand):
    help = "Export PurchasePayable data for all tenants"

    def handle(self, *args, **options):
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name="public")

        for tenant in tenants:
            self.stdout.write(
                self.style.SUCCESS(f"\nProcessing tenant: {tenant.schema_name}")
            )

            with schema_context(tenant.schema_name):
                payables = PurchasePayable.objects.all()
                result = []

                for item in payables:
                    result.append(
                        {
                            "id": item.id,
                            "vendor_no": (
                                getattr(item.vendor_no.no_series, "code", None)
                                if item.vendor_no
                                else None
                            ),
                            "purchase_no": (
                                getattr(item.purchase_no.no_series, "code", None)
                                if item.purchase_no
                                else None
                            ),
                            "invoice_no": (
                                getattr(item.invoice_no.no_series, "code", None)
                                if item.invoice_no
                                else None
                            ),
                            "posted_invoice_no": (
                                getattr(item.posted_invoice_no.no_series, "code", None)
                                if item.posted_invoice_no
                                else None
                            ),
                            "credit_memo_no": (
                                getattr(item.credit_memo_no.no_series, "code", None)
                                if item.credit_memo_no
                                else None
                            ),
                            "posted_credit_memo_no": (
                                getattr(
                                    item.posted_credit_memo_no.no_series, "code", None
                                )
                                if item.posted_credit_memo_no
                                else None
                            ),
                        }
                    )

                output = json.dumps(result, indent=4)
                filename = f"purchase_payables_{tenant.schema_name}.json"
                with open(filename, "w") as f:
                    f.write(output)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Exported {len(result)} records to {filename}"
                    )
                )
