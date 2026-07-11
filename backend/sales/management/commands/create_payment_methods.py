from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from company.models import Company
from financials.management.commands.seed_payment_methods import ensure_default_payment_methods
from financials.models import PaymentMethod


class Command(BaseCommand):
    help = "Create default payment methods for all company tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Limit to a single tenant schema",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        if schema_name:
            schemas = [schema_name]
        else:
            schemas = list(
                Company.objects.exclude(schema_name="public")
                .order_by("schema_name")
                .values_list("schema_name", flat=True)
            )

        total_created = 0
        for schema in schemas:
            self.stdout.write(f"\nProcessing tenant: {schema}")
            with schema_context(schema):
                before = PaymentMethod.objects.count()
                result = ensure_default_payment_methods()
                after = PaymentMethod.objects.count()
                created = after - before
                total_created += created

                if result.get("skipped"):
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Skipped — {result.get('reason', 'unknown reason')}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Payment methods: {before} -> {after} "
                            f"(cash G/L: {result.get('cash_gl', 'n/a')})"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted — {total_created} new payment method(s) across tenants."
            )
        )
