from django.core.management.base import BaseCommand
from django.db import transaction
from sales.models import Customer, SalesReceivable
from setup.models import NoSeries, NoSeriesLines
from datetime import datetime


class Command(BaseCommand):
    help = "Test customer no series functionality"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Testing Customer No Series Functionality...")
        )

        try:
            # Check if SalesReceivable setup exists
            sales_receivable = SalesReceivable.objects.all().first()
            if not sales_receivable:
                self.stdout.write(
                    self.style.WARNING(
                        "SalesReceivable setup not found. Creating test setup..."
                    )
                )

                # Check if CUSTOMER no series exists
                customer_no_series = NoSeries.objects.filter(code="CUSTOMER").first()
                if not customer_no_series:
                    self.stdout.write(
                        self.style.ERROR(
                            "CUSTOMER no series not found. Please run setup command first."
                        )
                    )
                    return

                # Create SalesReceivable setup
                customer_no_lines = NoSeriesLines.objects.filter(
                    no_series=customer_no_series
                ).first()
                if not customer_no_lines:
                    self.stdout.write(
                        self.style.ERROR(
                            "CUSTOMER no series lines not found. Please run setup command first."
                        )
                    )
                    return

                # Create minimal SalesReceivable setup for testing
                sales_receivable = SalesReceivable.objects.create(
                    customer_no=customer_no_lines,
                    invoice_no=customer_no_lines,  # Using same for testing
                    posted_invoice_no=customer_no_lines,  # Using same for testing
                )
                self.stdout.write(
                    self.style.SUCCESS("Created test SalesReceivable setup")
                )

            # Test creating customers
            self.stdout.write(self.style.SUCCESS("Creating test customers..."))

            # Create first customer
            customer1 = Customer.objects.create(
                name="Test Customer 1",
                address="Test Address 1",
                city="Test City 1",
                phone_number="+1234567890",
            )
            self.stdout.write(
                f"Created customer: {customer1.name} with number: {customer1.no}"
            )

            # Create second customer
            customer2 = Customer.objects.create(
                name="Test Customer 2",
                address="Test Address 2",
                city="Test City 2",
                phone_number="+0987654321",
            )
            self.stdout.write(
                f"Created customer: {customer2.name} with number: {customer2.no}"
            )

            # Create third customer
            customer3 = Customer.objects.create(
                name="Test Customer 3",
                address="Test Address 3",
                city="Test City 3",
                phone_number="+1122334455",
            )
            self.stdout.write(
                f"Created customer: {customer3.name} with number: {customer3.no}"
            )

            # Check the no series progression
            customer_no_lines = NoSeriesLines.objects.filter(
                no_series=sales_receivable.customer_no.no_series
            ).first()

            self.stdout.write(self.style.SUCCESS("No Series Status:"))
            self.stdout.write(f"  Start Number: {customer_no_lines.start_number}")
            self.stdout.write(
                f"  Last Used Number: {customer_no_lines.last_used_number}"
            )
            self.stdout.write(f"  Last Used Date: {customer_no_lines.last_used_date}")
            self.stdout.write(f"  Increment By: {customer_no_lines.increment_by}")

            # Clean up test customers
            self.stdout.write(self.style.WARNING("Cleaning up test customers..."))
            Customer.objects.filter(name__startswith="Test Customer").delete()

            self.stdout.write(
                self.style.SUCCESS("Customer No Series Test Completed Successfully!")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during test: {str(e)}"))
            raise
