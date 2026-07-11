"""
Management command to generate sales history for testing date filtering.

Generates 15 sales per day from November 3-7, 2025 (75 total sales).
All sales are created and posted automatically.
"""

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
import random

from sales.models import SalesInvoice, SalesInvoiceLine, Customer
from sales.admin import SalesInvoicePostingProcessor
from items.models import Item, Location, UnitOfMeasure, ItemUnitOfMeasure
from financials.models import PaymentMethod
from authentication.models import CustomUser


class Command(BaseCommand):
    help = "Generate sales history for testing (15 sales per day from Nov 3-7, 2025)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="hardwareworld",
            help="Tenant schema name",
        )
        parser.add_argument(
            "--sales-per-day",
            type=int,
            default=15,
            help="Number of sales to create per day (default: 15)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default="2025-11-03",
            help="Start date in YYYY-MM-DD format (default: 2025-11-03)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default="2025-11-07",
            help="End date in YYYY-MM-DD format (default: 2025-11-07)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating",
        )

    def handle(self, *args, **options):
        schema = options.get("schema", "hardwareworld")
        sales_per_day = options.get("sales_per_day", 15)
        start_date_str = options.get("start_date", "2025-11-03")
        end_date_str = options.get("end_date", "2025-11-07")
        dry_run = options.get("dry_run", False)

        # Parse dates
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        with schema_context(schema):
            # Step 1: Get available resources
            self.stdout.write("Step 1: Gathering resources...")
            
            # Get items with stock
            items_with_stock = []
            for item in Item.objects.all()[:100]:
                stock = item.inventory
                if stock and stock > 0:
                    items_with_stock.append(item)
            
            if not items_with_stock:
                self.stdout.write(
                    self.style.ERROR("No items with stock available!")
                )
                return
            
            self.stdout.write(f"  Found {len(items_with_stock)} items with stock")
            
            # Get "General" customer specifically
            general_customer = Customer.objects.filter(
                name__icontains="general"
            ).first()
            if not general_customer:
                # Try to find any customer with "General" in name
                general_customer = Customer.objects.filter(
                    name__icontains="General"
                ).first()
            
            if not general_customer:
                # Fallback to first customer
                general_customer = Customer.objects.first()
                if not general_customer:
                    self.stdout.write(
                        self.style.ERROR("No customers found!")
                    )
                    return
            
            self.stdout.write(f"  Using customer: {general_customer.name} (ID: {general_customer.id})")
            
            # Get payment methods
            payment_methods = list(PaymentMethod.objects.all())
            if not payment_methods:
                self.stdout.write(
                    self.style.ERROR("No payment methods found!")
                )
                return
            
            self.stdout.write(f"  Found {len(payment_methods)} payment methods")
            
            # Get location
            location = Location.objects.first()
            if not location:
                self.stdout.write(
                    self.style.ERROR("No location found!")
                )
                return
            
            self.stdout.write(f"  Using location: {location.code}")
            
            # Get user for posting
            user = CustomUser.objects.filter(is_active=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR("No active user found!")
                )
                return
            
            self.stdout.write(f"  Using user: {user.email}")
            
            # Get default UOM
            default_uom, _ = UnitOfMeasure.objects.get_or_create(
                code="PCS", defaults={"description": "Pieces"}
            )
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\n=== DRY RUN MODE ===")
                )
                sales_per_day_list = [10, 12, 18, 20, 15]
                total_days = (end_date - start_date).days + 1
                total_sales = sum(sales_per_day_list[:total_days])
                self.stdout.write(f"Would create sales from {start_date} to {end_date}")
                self.stdout.write("Sales distribution per day:")
                for i, (d, count) in enumerate(zip(
                    [start_date + timedelta(days=x) for x in range(total_days)],
                    sales_per_day_list[:total_days]
                )):
                    self.stdout.write(f"  {d}: {count} sales")
                self.stdout.write(f"Total sales to create: {total_sales}")
                return
            
            # Step 2: Generate sales for each day with varying counts
            # Sales per day: [10, 12, 18, 20, 15] = 75 total
            sales_per_day_list = [10, 12, 18, 20, 15]
            
            self.stdout.write("\nStep 2: Creating sales invoices...")
            self.stdout.write("Sales distribution per day:")
            for i, (d, count) in enumerate(zip(
                [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)],
                sales_per_day_list
            )):
                self.stdout.write(f"  {d}: {count} sales")
            
            current_date = start_date
            day_index = 0
            total_created = 0
            total_posted = 0
            errors = []
            daily_totals = {}  # Track totals per day
            
            while current_date <= end_date:
                sales_count = sales_per_day_list[day_index] if day_index < len(sales_per_day_list) else sales_per_day
                self.stdout.write(f"\n  Processing {current_date} ({sales_count} sales)...")
                daily_totals[current_date] = {"count": 0, "amount": 0}
                
                for sale_num in range(1, sales_count + 1):
                    try:
                        with transaction.atomic():
                            # Use General customer and random payment method
                            customer = general_customer
                            payment_method = random.choice(payment_methods)
                            
                            # Select 1-3 random items
                            num_items = random.randint(1, 3)
                            selected_items = random.sample(
                                items_with_stock, min(num_items, len(items_with_stock))
                            )
                            
                            # Create invoice
                            invoice = SalesInvoice(
                                customer=customer,
                                document_date=current_date,
                                posting_date=current_date,
                                vat_date=current_date,
                                due_date=current_date,
                                status="Open",
                                payment_method=payment_method,
                            )
                            invoice.save()
                            
                            # Create lines
                            total_amount = 0
                            for item in selected_items:
                                # Get available stock
                                stock = item.inventory
                                if stock <= 0:
                                    continue
                                
                                # Random quantity (1-5, but not more than stock)
                                quantity = random.randint(1, min(5, stock))
                                
                                # Get or create item UOM
                                item_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                                    item=item,
                                    unit_of_measure=default_uom,
                                    defaults={"quantity_per_unit": 1, "default": True},
                                )
                                
                                # Use item's unit price or default to 1000
                                unit_price = item.unit_price or 1000
                                line_amount = quantity * unit_price
                                total_amount += line_amount
                                
                                # Create line
                                line = SalesInvoiceLine.objects.create(
                                    sales_invoice=invoice,
                                    item=item,
                                    description=item.item_name or item.no,
                                    location_code=location,
                                    quantity=quantity,
                                    unit_of_measure=default_uom,
                                    item_unit_of_measure=item_uom,
                                    unit_price=unit_price,
                                    line_discount_amount=0,
                                )
                            
                            # Update invoice totals
                            invoice.total_amount = total_amount
                            invoice.amount_received = total_amount
                            invoice.change_amount = 0
                            invoice.save()
                            
                            # Step 3: Post the invoice
                            try:
                                # Create a mock request object for the posting processor
                                # Capture user in closure
                                posting_user = user
                                class MockRequest:
                                    def __init__(self, user):
                                        self.user = user
                                
                                mock_request = MockRequest(posting_user)
                                receipt_no = f"RCP-{current_date.strftime('%Y%m%d')}-{sale_num:03d}"
                                
                                posting_processor = SalesInvoicePostingProcessor(
                                    invoice, mock_request, receipt_no
                                )
                                result = posting_processor.post()
                                
                                if result.get("success"):
                                    total_posted += 1
                                    daily_totals[current_date]["count"] += 1
                                    daily_totals[current_date]["amount"] += total_amount
                                    self.stdout.write(
                                        f"    [OK] Sale {sale_num}: {invoice.invoice_no} - {total_amount:,} (Posted)"
                                    )
                                else:
                                    errors.append(
                                        f"{invoice.invoice_no}: Posting failed - {result.get('message')}"
                                    )
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"    [WARN] Sale {sale_num}: {invoice.invoice_no} - Posting failed"
                                        )
                                    )
                                
                            except Exception as e:
                                errors.append(f"{invoice.invoice_no}: {str(e)}")
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"    [ERROR] Sale {sale_num}: {invoice.invoice_no} - Error: {str(e)}"
                                    )
                                )
                            
                            total_created += 1
                            
                    except Exception as e:
                        errors.append(f"Sale {sale_num} on {current_date}: {str(e)}")
                        self.stdout.write(
                            self.style.ERROR(
                                f"    [ERROR] Sale {sale_num}: Error - {str(e)}"
                            )
                        )
                
                current_date += timedelta(days=1)
                day_index += 1
            
            # Step 4: Summary and Verification
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("Generation Complete!"))
            self.stdout.write(f"  Total invoices created: {total_created}")
            self.stdout.write(f"  Total invoices posted: {total_posted}")
            
            if errors:
                self.stdout.write(self.style.WARNING(f"\n  Errors: {len(errors)}"))
                for error in errors[:10]:  # Show first 10 errors
                    self.stdout.write(f"    - {error}")
                if len(errors) > 10:
                    self.stdout.write(f"    ... and {len(errors) - 10} more errors")
            
            # Verify distribution and show totals per day
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("Sales Summary by Date:"))
            self.stdout.write("-" * 60)
            
            from django.db.models import Sum, Count
            
            current_date = start_date
            grand_total_count = 0
            grand_total_amount = 0
            
            while current_date <= end_date:
                # Query actual totals from database
                # Calculate total_amount from lines since it's a computed property
                invoices = SalesInvoice.objects.filter(
                    posting_date=current_date, 
                    status="Posted"
                ).prefetch_related('lines')
                count = invoices.count()
                # Sum total_amount from each line (total_amount is a property on lines)
                total_amount = sum(
                    sum(line.total_amount for line in inv.lines.all())
                    for inv in invoices
                )
                
                day_stats = {
                    'count': count,
                    'total_amount': total_amount
                }
                
                count = day_stats['count'] or 0
                amount = day_stats['total_amount'] or 0
                grand_total_count += count
                grand_total_amount += amount
                
                self.stdout.write(
                    f"  {current_date}: {count:2d} sales | Total: {amount:>12,} | "
                    f"Avg per sale: {amount // count if count > 0 else 0:>8,}"
                )
                current_date += timedelta(days=1)
            
            self.stdout.write("-" * 60)
            self.stdout.write(
                f"  GRAND TOTAL: {grand_total_count:2d} sales | Total Amount: {grand_total_amount:>12,}"
            )
            self.stdout.write("=" * 60)

