from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context
from items.models import Item


class Command(BaseCommand):
    help = "Check items with available stock"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="hardwareworld",
            help="Tenant schema name",
        )

    def handle(self, *args, **options):
        schema = options.get("schema", "hardwareworld")

        with schema_context(schema):
            items_with_stock = []
            for item in Item.objects.all()[:100]:
                stock = item.inventory
                if stock and stock > 0:
                    items_with_stock.append((item, stock))

            items_with_stock.sort(key=lambda x: x[1], reverse=True)

            self.stdout.write(f"\nItems with stock: {len(items_with_stock)}")
            self.stdout.write("\nTop 30 items by stock:")
            for i, (item, stock) in enumerate(items_with_stock[:30], 1):
                self.stdout.write(f"{i}. {item.no} - {item.item_name} (Qty: {stock})")

            return None
