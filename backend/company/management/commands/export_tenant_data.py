from django.core.management.base import BaseCommand
from django.core import serializers
from django.apps import apps
from datetime import datetime
from django_tenants.utils import tenant_context
from company.models import Company  # Your tenant model
import json


class Command(BaseCommand):
    help = "Export specified tables data for a tenant into a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "schema_name", type=str, help="The tenant schema name to export data from"
        )
        parser.add_argument("--output", type=str, help="Output file path", default=None)

    def handle(self, *args, **options):
        schema_name = options["schema_name"]

        try:
            # Get the tenant
            tenant = Company.objects.get(schema_name=schema_name)

            # Define the models to export
            models_to_export = [
                ("financials", "G_LAccount"),
                ("postings", "GeneralBusinessPostingGroup"),
                ("postings", "GeneralProductPostingGroup"),
                ("postings", "GeneralPostingSetup"),
                ("postings", "InventoryPostingGroup"),
                ("postings", "InventoryPostingSetup"),
                ("customers", "Customer"),
                ("customers", "PaymentMethod"),
                ("customers", "CustomerPostingGroup"),
                ("items", "UnitOfMeasure"),
                # ("items", "ItemCategory"),
            ]

            export_data = {
                "metadata": {
                    "schema_name": schema_name,
                    "tenant_name": tenant.name,
                    "export_date": datetime.now().isoformat(),
                    "version": "1.0",
                },
                "data": {},
            }

            # Use tenant context
            with tenant_context(tenant):
                for app_label, model_name in models_to_export:
                    self.stdout.write(f"Exporting {app_label}.{model_name}...")

                    try:
                        model = apps.get_model(app_label, model_name)

                        # Get queryset (no need to filter by tenant as we're in tenant context)
                        queryset = model.objects.all()

                        # Serialize the data, excluding system fields
                        serialized_data = []
                        for obj in queryset:
                            obj_data = {}
                            for field in obj._meta.fields:
                                # Skip system fields
                                if field.name not in [
                                    "id",
                                    "created_at",
                                    "updated_at",
                                    "system_id",
                                ]:
                                    value = getattr(obj, field.name)

                                    # Handle foreign key relationships
                                    if field.is_relation:
                                        if value is not None:
                                            # For foreign keys, store the code or name
                                            if hasattr(value, "code"):
                                                obj_data[field.name] = value.code
                                            elif hasattr(value, "name"):
                                                obj_data[field.name] = value.name
                                            else:
                                                obj_data[field.name] = str(value)
                                    else:
                                        obj_data[field.name] = value

                            serialized_data.append(obj_data)

                        export_data["data"][
                            f"{app_label}.{model_name}"
                        ] = serialized_data

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully exported {len(serialized_data)} records from {model_name}"
                            )
                        )

                    except LookupError as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Could not find model {model_name} in app {app_label}: {str(e)}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Error exporting {model_name}: {str(e)}")
                        )

                # Generate output filename if not provided
                output_file = (
                    options["output"]
                    or f"tenant_{schema_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

                # Write to file
                with open(output_file, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully exported data to {output_file}")
                )

        except Company.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Tenant with schema name '{schema_name}' does not exist"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Export failed: {str(e)}"))
