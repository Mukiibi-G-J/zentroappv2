"""
Write sample invoice + receipt PDFs to disk for visual QA (logo, layout).

Usage:
  python manage.py generate_sample_billing_pdfs
  python manage.py generate_sample_billing_pdfs --out C:\\temp\\zentro_pdf_samples

Files created:
  sample-invoice.pdf
  sample-receipt.pdf
"""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from company.billing_receipt_email import (
    generate_invoice_pdf_bytes,
    generate_receipt_pdf_bytes,
)


def _mock_billing():
    return SimpleNamespace(
        metadata={"payer_email": "you@example.com", "user_reference": "40223076804"},
        status="paid",
        reference_number="#SAMPLE-36006",
        gateway_payment_id="ZENTRO-SAMPLE-MM-REF",
        company=SimpleNamespace(
            name="Sample Company Ltd",
            email="billing@samplecompany.test",
        ),
        product="Starter (monthly)",
        currency="UGX",
        amount=50_000,
        billing_date=date(2026, 5, 1),
        verified_at=timezone.make_aware(datetime(2026, 5, 1, 14, 30, 0)),
        verified_by=SimpleNamespace(
            email="info@zentroapp.app",
            get_full_name=lambda: "Zentro",
        ),
    )


class Command(BaseCommand):
    help = "Generate sample invoice and receipt PDFs for manual review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            type=str,
            default="",
            help="Output directory (default: <BASE_DIR>/tmp/sample_billing_pdfs)",
        )

    def handle(self, *args, **options):
        out_dir = options["out"].strip()
        if out_dir:
            target = Path(out_dir).resolve()
        else:
            target = Path(settings.BASE_DIR) / "tmp" / "sample_billing_pdfs"
        target.mkdir(parents=True, exist_ok=True)

        billing = _mock_billing()
        invoice_path = target / "sample-invoice.pdf"
        receipt_path = target / "sample-receipt.pdf"

        invoice_path.write_bytes(generate_invoice_pdf_bytes(billing))
        receipt_path.write_bytes(generate_receipt_pdf_bytes(billing))

        logo = Path(settings.BASE_DIR) / "static" / "images" / "logo" / "logo-light-full.png"
        self.stdout.write(self.style.SUCCESS("Wrote:"))
        self.stdout.write(f"  {invoice_path}")
        self.stdout.write(f"  {receipt_path}")
        if logo.is_file():
            self.stdout.write(self.style.SUCCESS(f"Logo file found: {logo}"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"No logo at {logo} — PDFs use the “Zentro” text fallback."
                )
            )
