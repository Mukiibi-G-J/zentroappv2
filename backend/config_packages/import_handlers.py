import pandas as pd
import logging
from difflib import get_close_matches
from django.db import transaction, models
from items.models import (
    Item,
    UnitOfMeasure,
    ItemCategory,
    ItemUnitOfMeasure,
    ItemTrackingCodes,
)
from postings.models import GeneralProductPostingGroup, InventoryPostingGroup
from items.models import Location, ItemJournal
from items.models import TrackingSpecification

logger = logging.getLogger(__name__)


def _suggest_match(value, valid_values, n=3, cutoff=0.5):
    """Return fuzzy-match suggestions for a value against a list of valid strings."""
    matches = get_close_matches(str(value), [str(v) for v in valid_values], n=n, cutoff=cutoff)
    if matches:
        return f" Did you mean: {', '.join(matches)}?"
    return ""


class BaseImportHandler:
    """Base class for all import handlers"""

    def __init__(self, model, tenant, package_table, user=None):
        self.model = model
        self.tenant = tenant
        self.package_table = package_table
        self.user = user
        self.stats = {
            "created": 0,
            "updated": 0,
            "failed": 0,
            "total_rows": 0,
            "errors": [],
        }

    def process_row(self, row_index, row_data, mapped_data):
        """Process a single row - to be implemented by subclasses"""
        raise NotImplementedError

    def validate_data(self, mapped_data):
        """Validate data before saving - to be implemented by subclasses"""
        return True, None

    def get_identifier_fields(self):
        """Get identifier fields for the model - to be implemented by subclasses"""
        return ["id", "code", "no", "name", "email"]

    def get_excluded_fields(self):
        """Get fields to exclude from import"""
        return {
            "id",
            "created_at",
            "updated_at",
            "system_id",
            "tree_id",
            "lft",
            "rght",
            "level",
            "password",
            "last_login",
            "start_date",
            "schema_name",
        }

    def get_required_fields(self):
        """Get required fields for the model - to be implemented by subclasses"""
        return []

    def get_backend_default_fields(self):
        """Get backend default fields that can be empty"""
        return set()


class ItemsImportHandler(BaseImportHandler):
    """Handler for importing Items"""

    def __init__(self, model, tenant, package_table, user=None):
        super().__init__(model, tenant, package_table, user)
        self.dependent_fields = ["sales_unit_of_measure", "purchase_unit_of_measure"]

    def get_identifier_fields(self):
        return ["no"]

    def get_required_fields(self):
        return ["item_name"]

    def get_backend_default_fields(self):
        return {
            "Costing Method",
            "Type",
            "Blocked",
            "Inventory Posting Group",
            "General Product Posting Group",
            "Tracking Code",
        }

    def validate_data(self, mapped_data):
        if not mapped_data.get("item_name"):
            return False, "Item Name is required"
        return True, None

    def process_foreign_keys(self, mapped_data, row_index):
        validation_errors = []
        row_label = f"Row {row_index + 5}"

        # Handle UnitOfMeasure
        if "unit_of_measure" in mapped_data and mapped_data["unit_of_measure"]:
            val = mapped_data["unit_of_measure"]
            unit_obj = UnitOfMeasure.objects.filter(code=val).first()
            if not unit_obj:
                unit_obj = UnitOfMeasure.objects.filter(code__iexact=val).first()
            if not unit_obj:
                valid = list(UnitOfMeasure.objects.values_list("code", flat=True))
                hint = _suggest_match(val, valid)
                validation_errors.append(
                    f"{row_label}: Unit of Measure '{val}' not found.{hint}"
                )
            else:
                mapped_data["unit_of_measure"] = unit_obj

        # Handle ItemCategory
        if "item_category" in mapped_data and mapped_data["item_category"]:
            val = mapped_data["item_category"]
            category_obj = ItemCategory.objects.filter(code=val).first()
            if not category_obj:
                category_obj = ItemCategory.objects.filter(code__iexact=val).first()
            if not category_obj:
                valid = list(ItemCategory.objects.values_list("code", flat=True))
                hint = _suggest_match(val, valid)
                validation_errors.append(
                    f"{row_label}: Item Category '{val}' not found.{hint}"
                )
            else:
                mapped_data["item_category"] = category_obj

        # Handle GeneralProductPostingGroup
        if (
            "general_product_posting_group" in mapped_data
            and mapped_data["general_product_posting_group"]
        ):
            val = mapped_data["general_product_posting_group"]
            posting_group_obj = GeneralProductPostingGroup.objects.filter(
                code=val
            ).first()
            if not posting_group_obj:
                posting_group_obj = GeneralProductPostingGroup.objects.filter(
                    code__iexact=val
                ).first()
            if not posting_group_obj:
                valid = list(GeneralProductPostingGroup.objects.values_list("code", flat=True))
                hint = _suggest_match(val, valid)
                validation_errors.append(
                    f"{row_label}: General Product Posting Group '{val}' not found.{hint}"
                )
            else:
                mapped_data["general_product_posting_group"] = posting_group_obj

        # Handle InventoryPostingGroup
        if (
            "inventory_posting_group" in mapped_data
            and mapped_data["inventory_posting_group"]
        ):
            val = mapped_data["inventory_posting_group"]
            inventory_group_obj = InventoryPostingGroup.objects.filter(
                code=val
            ).first()
            if not inventory_group_obj:
                inventory_group_obj = InventoryPostingGroup.objects.filter(
                    code__iexact=val
                ).first()
            if not inventory_group_obj:
                valid = list(InventoryPostingGroup.objects.values_list("code", flat=True))
                hint = _suggest_match(val, valid)
                validation_errors.append(
                    f"{row_label}: Inventory Posting Group '{val}' not found.{hint}"
                )
            else:
                mapped_data["inventory_posting_group"] = inventory_group_obj

        # Handle Tracking Code
        if "tracking_code" in mapped_data and mapped_data["tracking_code"]:
            val = mapped_data["tracking_code"]
            tracking_code_obj = ItemTrackingCodes.objects.filter(code=val).first()
            if not tracking_code_obj:
                tracking_code_obj = ItemTrackingCodes.objects.filter(
                    code__iexact=val
                ).first()
            if not tracking_code_obj:
                valid = list(ItemTrackingCodes.objects.values_list("code", flat=True))
                hint = _suggest_match(val, valid)
                validation_errors.append(
                    f"{row_label}: Tracking Code '{val}' not found.{hint}"
                )
            else:
                mapped_data["tracking_code"] = tracking_code_obj

        return validation_errors

    def process_dependent_fields(self, obj, dependent_field_values, row_index):
        if not dependent_field_values:
            return

        for field_name, value in dependent_field_values.items():
            try:
                unit_of_measure = UnitOfMeasure.objects.filter(code=value).first()
                if not unit_of_measure:
                    logger.warning(
                        f"Row {row_index + 5}: Unit of Measure '{value}' not found for {field_name}"
                    )
                    continue

                item_uom, created = ItemUnitOfMeasure.objects.get_or_create(
                    item=obj,
                    unit_of_measure=unit_of_measure,
                    defaults={"quantity_per_unit": 1},
                )

                setattr(obj, field_name, item_uom)
                obj.save()

            except Exception as e:
                logger.warning(
                    f"Row {row_index + 5}: Error processing {field_name} '{value}': {str(e)}"
                )

    def process_row(self, row_index, row_data, mapped_data):
        try:
            # Store dependent field values
            dependent_field_values = {}
            for field_name in self.dependent_fields:
                if field_name in mapped_data and mapped_data[field_name]:
                    dependent_field_values[field_name] = mapped_data[field_name]
                    del mapped_data[field_name]

            # Process foreign keys
            validation_errors = self.process_foreign_keys(mapped_data, row_index)
            if validation_errors:
                self.stats["errors"].extend(validation_errors)
                self.stats["failed"] += 1
                return False

            # Validate data
            is_valid, error_message = self.validate_data(mapped_data)
            if not is_valid:
                error_msg = f"Row {row_index + 5}: {error_message}"
                self.stats["errors"].append(error_msg)
                self.stats["failed"] += 1
                logger.warning(error_msg)
                return False

            # Determine identifier field
            identifier_field = (
                "no" if "no" in mapped_data and mapped_data["no"] else "item_name"
            )

            # Save to actual model table
            try:
                if identifier_field == "item_name":
                    existing_item_by_name = Item.objects.filter(
                        item_name=mapped_data["item_name"]
                    ).first()
                    if existing_item_by_name:
                        obj = existing_item_by_name
                        for key, value in mapped_data.items():
                            if key != "no":
                                setattr(obj, key, value)
                        obj.save()
                        self.stats["updated"] += 1
                    else:
                        obj = Item.objects.create(**mapped_data)
                        self.stats["created"] += 1
                else:
                    filter_kwargs = {identifier_field: mapped_data[identifier_field]}
                    try:
                        obj = Item.objects.get(**filter_kwargs)
                        for key, value in mapped_data.items():
                            setattr(obj, key, value)
                        obj.save()
                        self.stats["updated"] += 1
                    except Item.DoesNotExist:
                        obj = Item.objects.create(**mapped_data)
                        self.stats["created"] += 1

                # Process dependent fields
                self.process_dependent_fields(obj, dependent_field_values, row_index)

                # Update package table data
                self.update_package_table_data(mapped_data, identifier_field)

                return True

            except Exception as e:
                error_msg = f"Row {row_index + 5}: Error saving record: {str(e)}"
                self.stats["errors"].append(error_msg)
                self.stats["failed"] += 1
                logger.error(error_msg)
                return False

        except Exception as e:
            error_msg = f"Row {row_index + 5}: Error processing row: {str(e)}"
            self.stats["errors"].append(error_msg)
            self.stats["failed"] += 1
            logger.error(error_msg)
            return False

    def update_package_table_data(self, mapped_data, identifier_field):
        existing_records = self.package_table.data or []
        record_exists = False

        serializable_data = {}
        for key, value in mapped_data.items():
            if hasattr(value, "__str__"):
                serializable_data[key] = str(value)
            else:
                serializable_data[key] = value

        for i, record in enumerate(existing_records):
            if record.get(identifier_field) == serializable_data[identifier_field]:
                existing_records[i].update(serializable_data)
                record_exists = True
                break

        if not record_exists:
            existing_records.append(serializable_data)

        self.package_table.data = existing_records
        self.package_table.save()


class ItemJournalImportHandler(BaseImportHandler):
    """Handler for importing Item Journals"""

    def __init__(self, model, tenant, package_table, user=None):
        super().__init__(model, tenant, package_table, user)
        logger.info(f"DEBUG: ItemJournalImportHandler created with user: {self.user}")
        self.dependent_fields = []

    def get_identifier_fields(self):
        return ["document_no", "item"]

    def get_required_fields(self):
        return ["item"]

    def get_backend_default_fields(self):
        return {
            "Entry Type",
            "Description",
            "Quantity",
            "Unit Amount",
            "Amount",
            "Unit Cost",
            "Location Code",
            "Date",
            "Status",
        }

    def validate_data(self, mapped_data):
        if not mapped_data.get("item"):
            return False, "Item is required"
        return True, None

    def process_foreign_keys(self, mapped_data, row_index):
        validation_errors = []

        # Handle Item
        if "item" in mapped_data and mapped_data["item"]:
            # Try to find item by item_name first
            item_obj = Item.objects.filter(item_name=mapped_data["item"]).first()
            if not item_obj:
                # If not found by item_name, try by no
                item_obj = Item.objects.filter(no=mapped_data["item"]).first()
            if not item_obj:
                validation_errors.append(
                    f"Row {row_index + 5}: Item '{mapped_data['item']}' not found"
                )
            else:
                mapped_data["item"] = item_obj

        # Handle ItemUnitOfMeasure - automatically set based on item and unit of measure code
        if "item" in mapped_data and mapped_data["item"]:
            item_obj = mapped_data["item"]
            unit_of_measure_code = mapped_data.get("item_unit_of_measure", "PCS")

            # Try to find the ItemUnitOfMeasure for this specific item and unit of measure
            uom_obj = ItemUnitOfMeasure.objects.filter(
                item=item_obj, unit_of_measure__code=unit_of_measure_code
            ).first()

            if not uom_obj:
                # If not found, try to create it or use the default
                try:
                    from items.models import UnitOfMeasure

                    unit_of_measure = UnitOfMeasure.objects.get_or_create(
                        code=unit_of_measure_code,
                        defaults={"description": unit_of_measure_code},
                    )[0]

                    uom_obj = ItemUnitOfMeasure.objects.get_or_create(
                        item=item_obj,
                        unit_of_measure=unit_of_measure,
                        defaults={"quantity_per_unit": 1},
                    )[0]

                    logger.info(
                        f"Created ItemUnitOfMeasure: {uom_obj} for item {item_obj}"
                    )
                except Exception as e:
                    logger.error(f"Error creating ItemUnitOfMeasure: {e}")
                    validation_errors.append(
                        f"Row {row_index + 5}: Could not create Item Unit of Measure '{unit_of_measure_code}' for item '{item_obj.item_name}'"
                    )

            if uom_obj:
                mapped_data["item_unit_of_measure"] = uom_obj

        # Handle Location
        if "location_code" in mapped_data and mapped_data["location_code"]:
            location_obj = Location.objects.filter(
                code=mapped_data["location_code"]
            ).first()
            if not location_obj:
                validation_errors.append(
                    f"Row {row_index + 5}: Location '{mapped_data['location_code']}' not found"
                )
            else:
                mapped_data["location_code"] = location_obj

        return validation_errors

    def map_excel_columns(self, row_data):
        """Map Excel columns to model fields for ItemJournal"""
        mapped_data = {}

        # Define the mapping from Excel column names to model field names
        column_mapping = {
            "Entry Type": "entry_type",
            "Unit Cost": "unit_cost",
            "Unit Amount": "unit_amount",
            "Quantity": "quantity",
            "Location Code": "location_code",
            "Item": "item",
            "Description": "description",
            "Date": "date",
            "Status": "status",
            "Item Unit Of Measure": "item_unit_of_measure",
        }

        # Get model fields to understand field types
        model_fields = {field.name: field for field in self.model._meta.get_fields()}

        for excel_col, value in row_data.items():
            if value != "" and value is not None:
                # Use the mapping if available, otherwise use the default conversion
                if excel_col in column_mapping:
                    field_name = column_mapping[excel_col]
                else:
                    field_name = excel_col.lower().replace(" ", "_")

                # Validate that the field exists in the model
                if field_name in model_fields:
                    field = model_fields[field_name]

                    # Handle numeric fields - only convert if the value looks numeric
                    if isinstance(
                        field,
                        (
                            models.IntegerField,
                            models.FloatField,
                            models.DecimalField,
                            models.PositiveIntegerField,
                        ),
                    ):
                        try:
                            # Try to convert to the appropriate numeric type
                            if str(value).replace(".", "").replace(",", "").isdigit():
                                # Convert to float first, then to the appropriate type
                                float_value = float(str(value).replace(",", ""))

                                if isinstance(
                                    field,
                                    (models.IntegerField, models.PositiveIntegerField),
                                ):
                                    # For integer fields, convert to int
                                    mapped_data[field_name] = int(float_value)
                                else:
                                    # For float/decimal fields, keep as float
                                    mapped_data[field_name] = float_value
                            else:
                                # Skip this field if it's not numeric
                                continue
                        except (ValueError, TypeError):
                            # Skip this field if conversion fails
                            continue
                    else:
                        # For non-numeric fields, just assign the value
                        mapped_data[field_name] = value
                else:
                    # Field doesn't exist in model, skip it
                    continue

        return mapped_data

    def process_row(self, row_index, row_data, mapped_data):
        try:
            # Use custom column mapping for ItemJournal
            mapped_data = self.map_excel_columns(row_data)

            # Set the user field if we have user
            if self.user:
                mapped_data["user"] = self.user
                logger.info(f"DEBUG: Set user field to: {self.user}")
            else:
                logger.info(f"DEBUG: No user provided: {self.user}")
                # If no user provided, try to get the first available user in the tenant
                from authentication.models import CustomUser

                try:
                    first_user = CustomUser.objects.first()
                    if first_user:
                        mapped_data["user"] = first_user
                        logger.info(f"DEBUG: Using first available user: {first_user}")
                    else:
                        logger.error("DEBUG: No users found in tenant")
                except Exception as e:
                    logger.error(f"DEBUG: Error getting first user: {e}")

            # Validate required fields
            is_valid, error_message = self.validate_data(mapped_data)
            if not is_valid:
                self.stats["errors"].append(f"Row {row_index + 5}: {error_message}")
                self.stats["failed"] += 1
                return False

            # Process foreign keys
            validation_errors = self.process_foreign_keys(mapped_data, row_index)
            if validation_errors:
                self.stats["errors"].extend(validation_errors)
                self.stats["failed"] += 1
                return False

            # Check if record exists - try document_no first, then item
            existing_record = None
            identifier_field = None

            # Try to find existing record by document_no if it exists
            if "document_no" in mapped_data and mapped_data["document_no"]:
                existing_record = self.model.objects.filter(
                    document_no=mapped_data["document_no"]
                ).first()
                identifier_field = "document_no"
            # If no document_no or no existing record, try to find by item and other unique fields
            elif "item" in mapped_data and mapped_data["item"]:
                # For ItemJournal, we might want to check for existing records with same item, entry_type, and date
                filter_kwargs = {"item": mapped_data["item"]}
                if "entry_type" in mapped_data and mapped_data["entry_type"]:
                    filter_kwargs["entry_type"] = mapped_data["entry_type"]
                if "date" in mapped_data and mapped_data["date"]:
                    filter_kwargs["date"] = mapped_data["date"]

                existing_record = self.model.objects.filter(**filter_kwargs).first()
                identifier_field = "item"

            # Prepare data for saving
            save_data = {}
            for field_name, value in mapped_data.items():
                if field_name in self.get_excluded_fields():
                    continue
                save_data[field_name] = value

            logger.info(f"DEBUG: save_data keys: {list(save_data.keys())}")
            logger.info(f"DEBUG: user in save_data: {save_data.get('user')}")

            # Save or update record
            if existing_record:
                for field_name, value in save_data.items():
                    setattr(existing_record, field_name, value)
                existing_record.save()
                self.stats["updated"] += 1

                # Update package table data
                self.update_package_table_data(save_data, identifier_field)
            else:
                new_record = self.model.objects.create(**save_data)
                self.stats["created"] += 1

                # Update package table data
                self.update_package_table_data(save_data, identifier_field)

            return True

        except Exception as e:
            error_msg = f"Row {row_index + 5}: Error saving record: {str(e)}"
            self.stats["errors"].append(error_msg)
            self.stats["failed"] += 1
            logger.error(error_msg)
            return False

    def update_package_table_data(self, mapped_data, identifier_field):
        existing_records = self.package_table.data or []
        record_exists = False

        serializable_data = {}
        for key, value in mapped_data.items():
            if hasattr(value, "__str__"):
                serializable_data[key] = str(value)
            else:
                serializable_data[key] = value

        # Only try to match existing records if we have an identifier field and value
        if identifier_field and identifier_field in serializable_data:
            for i, record in enumerate(existing_records):
                if record.get(identifier_field) == serializable_data[identifier_field]:
                    existing_records[i].update(serializable_data)
                    record_exists = True
                    break

        if not record_exists:
            existing_records.append(serializable_data)

        self.package_table.data = existing_records
        self.package_table.save()


class TrackingSpecificationImportHandler(BaseImportHandler):
    """Handler for importing Tracking Specifications"""

    def __init__(self, model, tenant, package_table, user=None):
        super().__init__(model, tenant, package_table, user)
        logger.info(
            f"DEBUG: TrackingSpecificationImportHandler created with user: {self.user}"
        )
        self.dependent_fields = []

    def get_identifier_fields(self):
        return ["lot_no", "serial_no"]

    def get_required_fields(self):
        return ["item"]

    def get_backend_default_fields(self):
        return {
            "description",
            "serial_no",
            "expiry_date",
        }

    def validate_data(self, mapped_data):
        if not mapped_data.get("item"):
            return False, "Item is required"
        return True, None

    def process_foreign_keys(self, mapped_data, row_index):
        validation_errors = []

        # Handle Item
        if "item" in mapped_data and mapped_data["item"]:
            # Try to find item by item_name first
            item_obj = Item.objects.filter(item_name=mapped_data["item"]).first()
            if not item_obj:
                # If not found by item_name, try by no
                item_obj = Item.objects.filter(no=mapped_data["item"]).first()
            if not item_obj:
                validation_errors.append(
                    f"Row {row_index + 5}: Item '{mapped_data['item']}' not found"
                )
            else:
                mapped_data["item"] = item_obj

        # Handle Location
        if "location_code" in mapped_data and mapped_data["location_code"]:
            location_obj = Location.objects.filter(
                code=mapped_data["location_code"]
            ).first()
            if not location_obj:
                validation_errors.append(
                    f"Row {row_index + 5}: Location '{mapped_data['location_code']}' not found"
                )
            else:
                mapped_data["location_code"] = location_obj

        # Handle ItemJournal - find the most recent ItemJournal for this item
        if "item" in mapped_data and mapped_data["item"]:
            item_obj = mapped_data["item"]
            # Find the most recent ItemJournal for this item
            item_journal = (
                ItemJournal.objects.filter(item=item_obj)
                .order_by("-created_at")
                .first()
            )

            if item_journal:
                mapped_data["item_journal"] = item_journal
                logger.info(f"Linked to ItemJournal: {item_journal.document_no}")
            else:
                logger.warning(f"No ItemJournal found for item: {item_obj.item_name}")

        return validation_errors

    def generate_lot_number(self, item_name):
        """Generate a unique lot number for the item"""
        import random
        import string

        # Create a base lot number from item name and random characters
        base_name = "".join(c for c in item_name if c.isalnum())[:3].upper()
        random_chars = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=4)
        )
        lot_number = f"{base_name}{random_chars}"

        # Ensure uniqueness
        counter = 1
        original_lot_number = lot_number
        while TrackingSpecification.objects.filter(lot_no=lot_number).exists():
            lot_number = f"{original_lot_number}{counter}"
            counter += 1

        return lot_number

    def map_excel_columns(self, row_data):
        """Map Excel columns to model fields for TrackingSpecification"""
        mapped_data = {}

        # Define the mapping from Excel column names to model field names
        column_mapping = {
            "Location Code": "location_code",
            "Lot No.": "lot_no",
            "Description": "description",
            "Item": "item",
            "Expiry Date": "expiry_date",
            "Quantity (Base)": "quantity_base",
            "Serial No.": "serial_no",
        }

        # Get model fields to understand field types
        model_fields = {field.name: field for field in self.model._meta.get_fields()}

        for excel_col, value in row_data.items():
            if value != "" and value is not None:
                # Use the mapping if available, otherwise use the default conversion
                if excel_col in column_mapping:
                    field_name = column_mapping[excel_col]
                else:
                    field_name = excel_col.lower().replace(" ", "_")

                # Validate that the field exists in the model
                if field_name in model_fields:
                    field = model_fields[field_name]

                    # Handle date fields
                    if isinstance(field, models.DateField):
                        try:
                            # Try to parse various date formats
                            if isinstance(value, str):
                                # Handle DD-MM-YY or MM-DD-YY formats
                                if len(value.split("-")) == 3:
                                    parts = value.split("-")
                                    if (
                                        len(parts[0]) == 2
                                        and len(parts[1]) == 2
                                        and len(parts[2]) == 2
                                    ):
                                        # Assume DD-MM-YY format
                                        day, month, year = parts
                                        # Convert 2-digit year to 4-digit
                                        if int(year) < 50:
                                            year = f"20{year}"
                                        else:
                                            year = f"19{year}"
                                        value = f"{year}-{month}-{day}"
                            mapped_data[field_name] = value
                        except Exception as e:
                            logger.warning(
                                f"Could not parse date '{value}' for field {field_name}: {e}"
                            )
                            continue

                    # Handle numeric fields
                    elif isinstance(
                        field,
                        (
                            models.IntegerField,
                            models.FloatField,
                            models.DecimalField,
                            models.PositiveIntegerField,
                        ),
                    ):
                        try:
                            if str(value).replace(".", "").replace(",", "").isdigit():
                                float_value = float(str(value).replace(",", ""))

                                if isinstance(
                                    field,
                                    (models.IntegerField, models.PositiveIntegerField),
                                ):
                                    mapped_data[field_name] = int(float_value)
                                else:
                                    mapped_data[field_name] = float_value
                            else:
                                continue
                        except (ValueError, TypeError):
                            continue
                    else:
                        # For non-numeric fields, just assign the value
                        mapped_data[field_name] = value
                else:
                    # Field doesn't exist in model, skip it
                    continue

        return mapped_data

    def process_row(self, row_index, row_data, mapped_data):
        try:
            # Use custom column mapping for TrackingSpecification
            mapped_data = self.map_excel_columns(row_data)

            # Set the user field if we have user
            if self.user:
                mapped_data["user"] = self.user
                logger.info(f"DEBUG: Set user field to: {self.user}")
            else:
                logger.info(f"DEBUG: No user provided: {self.user}")
                # If no user provided, try to get the first available user in the tenant
                from authentication.models import CustomUser

                try:
                    first_user = CustomUser.objects.first()
                    if first_user:
                        mapped_data["user"] = first_user
                        logger.info(f"DEBUG: Using first available user: {first_user}")
                    else:
                        logger.error("DEBUG: No users found in tenant")
                except Exception as e:
                    logger.error(f"DEBUG: Error getting first user: {e}")

            # Generate lot number if empty
            if not mapped_data.get("lot_no"):
                item_name = mapped_data.get("item", "Unknown")
                if isinstance(item_name, Item):
                    item_name = item_name.item_name
                lot_number = self.generate_lot_number(item_name)
                mapped_data["lot_no"] = lot_number
                logger.info(f"Generated lot number: {lot_number} for item: {item_name}")

            # Validate required fields
            is_valid, error_message = self.validate_data(mapped_data)
            if not is_valid:
                self.stats["errors"].append(f"Row {row_index + 5}: {error_message}")
                self.stats["failed"] += 1
                return False

            # Process foreign keys
            validation_errors = self.process_foreign_keys(mapped_data, row_index)
            if validation_errors:
                self.stats["errors"].extend(validation_errors)
                self.stats["failed"] += 1
                return False

            # Check if record exists - use lot_no and serial_no combination
            existing_record = None
            identifier_field = None

            if "lot_no" in mapped_data and mapped_data["lot_no"]:
                filter_kwargs = {"lot_no": mapped_data["lot_no"]}
                if "serial_no" in mapped_data and mapped_data["serial_no"]:
                    filter_kwargs["serial_no"] = mapped_data["serial_no"]
                elif "item" in mapped_data and mapped_data["item"]:
                    filter_kwargs["item"] = mapped_data["item"]

                existing_record = self.model.objects.filter(**filter_kwargs).first()
                identifier_field = "lot_no"

            # Prepare data for saving
            save_data = {}
            for field_name, value in mapped_data.items():
                if field_name in self.get_excluded_fields():
                    continue
                save_data[field_name] = value

            logger.info(f"DEBUG: save_data keys: {list(save_data.keys())}")
            logger.info(f"DEBUG: lot_no in save_data: {save_data.get('lot_no')}")

            # Save or update record
            if existing_record:
                for field_name, value in save_data.items():
                    setattr(existing_record, field_name, value)
                existing_record.save()
                self.stats["updated"] += 1

                # Update package table data
                self.update_package_table_data(save_data, identifier_field)
            else:
                new_record = self.model.objects.create(**save_data)
                self.stats["created"] += 1

                # Update package table data
                self.update_package_table_data(save_data, identifier_field)

            return True

        except Exception as e:
            error_msg = f"Row {row_index + 5}: Error saving record: {str(e)}"
            self.stats["errors"].append(error_msg)
            self.stats["failed"] += 1
            logger.error(error_msg)
            return False

    def update_package_table_data(self, mapped_data, identifier_field):
        existing_records = self.package_table.data or []
        record_exists = False

        serializable_data = {}
        for key, value in mapped_data.items():
            if hasattr(value, "__str__"):
                serializable_data[key] = str(value)
            else:
                serializable_data[key] = value

        # Only try to match existing records if we have an identifier field and value
        if identifier_field and identifier_field in serializable_data:
            for i, record in enumerate(existing_records):
                if record.get(identifier_field) == serializable_data[identifier_field]:
                    existing_records[i].update(serializable_data)
                    record_exists = True
                    break

        if not record_exists:
            existing_records.append(serializable_data)

        self.package_table.data = existing_records
        self.package_table.save()


# Import handler factory
def get_import_handler(model_name):
    """Factory function to get the appropriate import handler based on model name"""
    handlers = {
        "item": ItemsImportHandler,
        "item_journal": ItemJournalImportHandler,
        "itemjournal": ItemJournalImportHandler,  # Add the camelCase version
        "tracking_specification": TrackingSpecificationImportHandler,
        "trackingspecification": TrackingSpecificationImportHandler,  # Add the lowercase version
        # Add more handlers here as needed
    }

    return handlers.get(model_name.lower())


def get_validation_handler(model_name):
    """Factory function to get validation handler for a model"""
    handlers = {
        "item": lambda data: ItemsImportHandler.validate_data(None, data),
        "item_journal": lambda data: ItemJournalImportHandler.validate_data(None, data),
        "itemjournal": lambda data: ItemJournalImportHandler.validate_data(
            None, data
        ),  # Add the camelCase version
        "tracking_specification": lambda data: TrackingSpecificationImportHandler.validate_data(
            None, data
        ),
        "trackingspecification": lambda data: TrackingSpecificationImportHandler.validate_data(
            None, data
        ),  # Add the lowercase version
        # Add more validation handlers here as needed
    }

    return handlers.get(model_name.lower())


def get_relationship_handler(model_name):
    """Factory function to get relationship handler for a model"""
    handlers = {
        "item": lambda data, obj: ItemsImportHandler.process_dependent_fields(
            None, data, obj, 0
        ),
        "item_journal": lambda data, obj: ItemJournalImportHandler.process_dependent_fields(
            None, data, obj, 0
        ),
        "itemjournal": lambda data, obj: ItemJournalImportHandler.process_dependent_fields(
            None, data, obj, 0
        ),  # Add the camelCase version
        "tracking_specification": lambda data, obj: TrackingSpecificationImportHandler.process_dependent_fields(
            None, data, obj, 0
        ),
        "trackingspecification": lambda data, obj: TrackingSpecificationImportHandler.process_dependent_fields(
            None, data, obj, 0
        ),  # Add the lowercase version
        # Add more relationship handlers here as needed
    }

    return handlers.get(model_name.lower())


def process_import_data(model, tenant, package_table, data_df, user=None):
    """Main function to process import data using appropriate handler"""
    logger.info(f"DEBUG: process_import_data called with user: {user}")
    model_name = model._meta.model_name.lower()
    handler_class = get_import_handler(model_name)

    if not handler_class:
        raise ValueError(f"No import handler found for model: {model_name}")

    handler = handler_class(model, tenant, package_table, user)
    logger.info(f"DEBUG: Created handler with user: {handler.user}")
    handler.stats["total_rows"] = len(data_df)

    # Process each row
    for row_index, row in data_df.iterrows():
        row_data = row.to_dict()
        row_data = {k: ("" if pd.isna(v) else v) for k, v in row_data.items()}

        # For ItemJournal and TrackingSpecification, let the handler do its own mapping
        if model_name == "itemjournal":
            handler.process_row(row_index, row_data, {})
        elif (
            model_name == "tracking_specification"
            or model_name == "trackingspecification"
        ):
            handler.process_row(row_index, row_data, {})
        else:
            # Map Excel columns to model fields for other models
            mapped_data = {}
            for excel_col, value in row_data.items():
                if value != "" and value is not None:
                    field_name = excel_col.lower().replace(" ", "_")
                    mapped_data[field_name] = value

            # Process the row
            handler.process_row(row_index, row_data, mapped_data)

    return handler.stats
