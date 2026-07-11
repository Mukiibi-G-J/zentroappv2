from django.core.management.base import BaseCommand
from base.models import ObjectType as ObjType


class Command(BaseCommand):
    help = "Create initial ObjectTypes for permission system"

    def handle(self, *args, **options):
        object_types = [
            {
                "name": "Table",
                "code": "TABLE",
                "sort_order": 1,
                "description": "Database tables and models",
            },
            {
                "name": "Page",
                "code": "PAGE",
                "sort_order": 2,
                "description": "UI pages and views",
            },
            {
                "name": "Report",
                "code": "REPORT",
                "sort_order": 3,
                "description": "Reports and analytics",
            },
            {
                "name": "Codeunit",
                "code": "CODEUNIT",
                "sort_order": 4,
                "description": "Business logic and processes",
            },
            {
                "name": "Query",
                "code": "QUERY",
                "sort_order": 5,
                "description": "Data queries",
            },
            {
                "name": "API",
                "code": "API",
                "sort_order": 6,
                "description": "API endpoints",
            },
        ]

        for obj_type_data in object_types:
            obj_type, created = ObjType.objects.get_or_create(
                code=obj_type_data["code"], defaults=obj_type_data
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created ObjectType: {obj_type.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"  ObjectType already exists: {obj_type.name}")
                )

        self.stdout.write(self.style.SUCCESS("\n✓ Object types setup complete!"))
