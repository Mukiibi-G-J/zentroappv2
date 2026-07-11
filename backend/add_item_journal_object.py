#!/usr/bin/env python
import os
import django
from django.db import models

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from base.models import Objects


def add_item_journal_object():
    """Add Item Journal object to the Objects table if it doesn't exist"""
    try:
        # Check if Item Journal object already exists
        existing = Objects.objects.filter(object_name="item_journal").first()

        if existing:
            print(f"Item Journal object already exists with ID: {existing.object_id}")
            return existing

        # Find the next available object_id
        max_id = (
            Objects.objects.aggregate(models.Max("object_id"))["object_id__max"] or 0
        )
        next_id = max_id + 1

        # Create the Item Journal object
        item_journal_obj = Objects.objects.create(
            object_type="Table",
            object_id=next_id,
            object_name="item_journal",
            object_caption="Item Journal",
            object_subtype="Custom",
            app_label="items",
        )

        print(f"Created Item Journal object with ID: {next_id}")
        return item_journal_obj

    except Exception as e:
        print(f"Error creating Item Journal object: {e}")
        return None


if __name__ == "__main__":
    add_item_journal_object()
