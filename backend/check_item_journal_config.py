#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from config_packages.models import ConfigPackage, ConfigPackageTable
from base.models import Objects


def check_and_create_item_journal_config():
    """Check if Item Journal has ConfigPackageTable records and create them if needed"""
    try:
        # Get the Item Journal object
        item_journal_obj = Objects.objects.filter(object_name="item_journal").first()

        if not item_journal_obj:
            print("Item Journal object not found in base.Objects table")
            return

        print(f"Found Item Journal object with ID: {item_journal_obj.object_id}")

        # Get all ConfigPackages
        packages = ConfigPackage.objects.all()

        for package in packages:
            print(f"Checking package: {package.code}")

            # Check if ConfigPackageTable record exists for this package and Item Journal
            existing_config = ConfigPackageTable.objects.filter(
                package_code=package, table_id=item_journal_obj
            ).first()

            if existing_config:
                print(
                    f"  - ConfigPackageTable record already exists for package {package.code}"
                )
                # Ensure field_config is populated
                if (
                    not existing_config.field_config
                    or "fields" not in existing_config.field_config
                ):
                    print(f"  - Populating field_config for package {package.code}")
                    existing_config.populate_field_config()
                    existing_config.save()
                    print(
                        f"  - Field config populated: {len(existing_config.field_config.get('fields', []))} fields"
                    )
            else:
                print(
                    f"  - Creating ConfigPackageTable record for package {package.code}"
                )
                # Create new ConfigPackageTable record
                config_table = ConfigPackageTable.objects.create(
                    package_code=package,
                    table_id=item_journal_obj,
                    table_name="item_journal",
                )
                print(
                    f"  - Created ConfigPackageTable record with ID: {config_table.id}"
                )
                print(
                    f"  - Field config populated: {len(config_table.field_config.get('fields', []))} fields"
                )

        print("Item Journal configuration check completed!")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_and_create_item_journal_config()
