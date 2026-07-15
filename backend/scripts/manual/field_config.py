#!/usr/bin/env python
"""
Test script for field configuration system
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from config_packages.models import ConfigPackage, ConfigPackageTable
from base.models import Objects
from django_tenants.utils import tenant_context
from company.models import Company


def test_field_configuration():
    """Test the field configuration system for GO-LIVE2 and item table"""

    # Get the first available tenant
    try:
        tenant = Company.objects.first()
        if not tenant:
            print("No tenants found. Please create a tenant first.")
            return
    except Exception as e:
        print(f"Error getting tenant: {e}")
        return

    print(f"Using tenant: {tenant.schema_name}")

    # Use tenant context
    with tenant_context(tenant):
        try:
            # Create a test package with code 'GO-LIVE2'
            package, created = ConfigPackage.objects.get_or_create(
                code="GO-LIVE2",
                defaults={"package_name": "Go Live Package", "status": "DRAFT"},
            )
            print(f"Package: {package.code} - {package.package_name}")

            # Create a test table object for 'item'
            table_obj, created = Objects.objects.get_or_create(
                object_id=9999,
                defaults={
                    "object_type": "Table",
                    "object_name": "item",
                    "object_caption": "Test Item Table",
                },
            )
            print(f"Table Object: {table_obj.object_name}")

            # Create a config table for 'item'
            config_table, created = ConfigPackageTable.objects.get_or_create(
                package_code=package,
                table_id=table_obj,
                defaults={
                    "table_name": "item",
                    "description": "Go Live item table configuration",
                },
            )
            print(f"Config Table: {config_table.table_name}")

            # Test field configuration population
            print("\n=== Testing Field Configuration ===")
            config_table.populate_field_config()
            print(f"Field Config: {config_table.field_config}")

            # Test getting default export fields
            print("\n=== Default Export Fields ===")
            export_fields = config_table.get_export_fields()
            print(f"Export Fields: {export_fields}")

            # Test adding a custom field (e.g., 'type')
            print("\n=== Adding Custom Field 'type' ===")
            config_table.update_field_config(custom_fields=["type"])
            print(f"Updated Field Config: {config_table.field_config}")
            print(f"Export Fields After Adding: {config_table.get_export_fields()}")

            # Test removing a default field (e.g., 'unit_price')
            print("\n=== Removing Default Field 'unit_price' ===")
            current_excluded = config_table.field_config.get("excluded_fields", [])
            config_table.update_field_config(
                excluded_fields=current_excluded + ["unit_price"]
            )
            print(f"Updated Field Config: {config_table.field_config}")
            print(f"Export Fields After Removing: {config_table.get_export_fields()}")

            print("\n=== Test Completed Successfully ===")

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_field_configuration()
