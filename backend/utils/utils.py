from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django_tenants.utils import schema_context
from django.urls import reverse


import pandas as pd
import uuid
import io
import threading
import time
import requests


class UUIField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 36
        kwargs["unique"] = True
        kwargs["editable"] = False
        kwargs["default"] = uuid.uuid4
        super().__init__(*args, **kwargs)


class BaseModel(models.Model):
    created_at = models.DateTimeField(
        verbose_name="Created At", auto_now_add=True, db_index=True
    )
    updated_at = models.DateTimeField(verbose_name="Updated At", auto_now=True)
    system_id = UUIField(verbose_name="System ID", db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["system_id"]),
        ]
        abstract = True


class SingletonSetupModel(BaseModel):
    """
    Business Central-style setup table: exactly one configuration row per tenant.
    """

    class Meta:
        abstract = True

    @classmethod
    def get_solo(cls):
        """Return the single setup row, or None if not seeded yet."""
        return cls.objects.first()

    def save(self, *args, **kwargs):
        if not self.pk and self.__class__.objects.exists():
            raise ValidationError(
                _("Only one %(name)s row is allowed.")
                % {"name": self._meta.verbose_name or self._meta.model_name}
            )
        super().save(*args, **kwargs)


class ExcelProcessor:
    def __init__(self, file, process_id, request):
        from config_packages.models import UploadTemplates
        from items.models import (
            Item,
            ItemJournal,
            UnitOfMeasure,
            ItemCategory,
            ItemLedgerEntries,
        )
        from items.enums import EntryType

        self.file_content = io.BytesIO(file.read())
        self.file_name = file.name
        self.process_id = process_id
        self.steps = [
            self.validate_file_format,
            self.read_file_content,
            self.process_data,
            self.validate_entries,
            self.save_to_database,
        ]
        self.request = request

        self.uploaded_data = []
        self.total_items_in_journal = 0
        self.upload_templates = UploadTemplates.objects.all()
        self.current_upload_template = None
        self.upload_class = UploadTemplates
        self.models = {
            "item": Item,
            "item journal": ItemJournal,
            "entry type": EntryType,
            "unit of measure": UnitOfMeasure,
            "item category": ItemCategory,
            "item ledger entries": ItemLedgerEntries,
        }
        self.enums = {
            "entry type": EntryType,
        }
        self.upload_data_summary = {
            "model_type": None,  # Will store the type of model being processed
            "total_records": 0,  # Total records processed
            "created_records": 0,  # New records created
            "updated_records": 0,  # Existing records updated
            "failed_records": 0,  # Records that failed processing
            "details": [],  # List for any specific details or errors
            "timestamp": timezone.now(),
            "url": None,
        }

    @classmethod
    def initialize_background_process(cls, file, process_id, request):
        try:
            processor = cls(file, process_id, request)
            thread = threading.Thread(target=processor.run, daemon=True)
            thread.start()
        except Exception as e:
            cache.set(
                f"upload_status_{process_id}",
                {"status": "failed", "progress": 0, "message": f"Error: {str(e)}"},
                timeout=3600,
            )
            return e

    def update_status(self, process, message, status="processing", summary=None):
        cache.set(
            f"upload_status_{self.process_id}",
            {
                "status": status,
                "progress": process,
                "message": message,
                "summary": summary,
            },
            timeout=3600,
        )
        time.sleep(1)

    def validate_file_format(self):
        self.update_status(20, "Validating file format...")
        if not self.file_name.endswith((".xlsx", ".xls")):
            self.update_status(
                0,
                "Invalid file format. Please upload a valid Excel file.",
                status="failed",
            )
            raise ValueError("Invalid file format. Please upload a valid Excel file.")

        time.sleep(1.5)

    def read_file_content(self):
        self.df = pd.read_excel(self.file_content, header=None)
        header_cell = str(self.df.iloc[0, 0]).replace(" ", "")  # Gets 'ITEM'
        uploaded_columns = [
            str(col).strip().upper() for col in self.df.iloc[1].tolist()
        ]  # Gets row with ITEM_NAME, etc....
        template_names = [
            str(value).upper().replace(" ", "")
            for value in list(self.upload_templates.values_list("name", flat=True))
        ]
        print(template_names)
        print(header_cell)
        # Validate if this is the correct template
        if header_cell not in template_names:
            self.update_status(
                0,
                f"Invalid template. Please upload the template downloaded from the system.",
                status="failed",
            )
            raise ValueError(
                f"Invalid template format. Please upload the template downloaded from the system."
            )

        self.current_upload_template = self.upload_class.objects.get(
            name=str(header_cell).lower()
        )

        if not self.current_upload_template:
            self.update_status(
                0,
                f"Invalid template. Please upload the template downloaded from the system.",
                status="failed",
            )
            raise ValueError(
                f"Invalid template. Please upload the template downloaded from the system."
            )

        # check if their is a missing
        template_url = self.current_upload_template.template_file.url
        expected_columns = self.get_template_columns_from_url(template_url)
        missing_columns = [
            col for col in expected_columns if col not in uploaded_columns
        ]
        if missing_columns:
            self.update_status(
                0, f"Missing columns: {missing_columns}", status="failed"
            )
            raise ValueError(f"Missing columns: {missing_columns}")

        # check if file is empty row 3
        if len(self.df) <= 2:
            self.update_status(0, "File is empty", status="failed")
            raise ValueError("File is empty")

        # self.df = self.df[self.df.iloc[:, 0].notna()]

        # set the column names to the second row
        self.df.columns = self.df.iloc[1]

        # Drop the first two rows (original row 0 and row 1)
        self.df = self.df[2:].reset_index(drop=True)

        # drop empty rows with all null values except the row with empty CATEGORY_STEP1
        if (
            "CATEGORY_STEP1" in self.df.columns
            and self.current_upload_template.name == "item"
        ):
            self.df = self.df.dropna(
                subset=[col for col in self.df.columns if col != "CATEGORY_STEP1"],
                how="any",
            )

        if (
            "SUBCATEGORY" in self.df.columns
            and self.current_upload_template.name == "item category"
        ):
            self.df = self.df.dropna(
                subset=[col for col in self.df.columns if col != "SUBCATEGORY"],
                how="any",
            )
        self.update_status(40, "Reading file content...")
        time.sleep(1.5)

    def process_data(self):
        try:
            self.update_status(60, "Processing data...")
            model_name = self.current_upload_template.name.lower()
            print(model_name)
            match model_name:
                case "item":
                    self.process_item_data()
                case "itemcategory":
                    self.process_item_categories_data()
                case "itemsonly":
                    self.process_item_only_data()
                case "itemledgerentries":
                    self.process_item_ledger_data()
                case "itemjournal":
                    self.process_item_journal_data()
        except Exception as e:
            self.update_status(0, f"Error processing data: {str(e)}", status="failed")
            raise ValueError(f"Error processing data: {str(e)}")

        time.sleep(1.5)

    def validate_entries(self):
        self.update_status(80, "Validating entries...")
        time.sleep(1.5)

    def save_to_database(self):
        self.update_status(90, "Saving to database...")
        time.sleep(1.5)

    def run(self):
        try:
            for step in self.steps:
                try:
                    step()
                except Exception as e:
                    self.update_status(process=0, message=str(e), status="failed")
                    return
            summary = {
                "model_type": self.upload_data_summary["model_type"],
                "total_records": self.upload_data_summary["total_records"],
                "created_records": self.upload_data_summary["created_records"],
                "updated_records": self.upload_data_summary["updated_records"],
                "failed_records": self.upload_data_summary["failed_records"],
                "details": self.upload_data_summary["details"],
                "timestamp": self.upload_data_summary["timestamp"],
                "url": self.upload_data_summary["url"],
            }
            self.update_status(
                100,
                "File processing completed successfully!",
                status="completed",
                summary=summary,
            )
        except Exception as e:
            print(e)
            self.update_status(process=0, message=str(e), status="failed")

    def get_template_columns_from_url(self, template_url):
        """
        Read column names from the template file URL
        """
        try:
            # Download the template file from S3
            response = requests.get(template_url)
            template_content = io.BytesIO(response.content)

            # Read the template Excel file
            template_df = pd.read_excel(template_content, header=None)

            # Get column names from second row (index 1)
            template_columns = template_df.iloc[1].tolist()

            # Clean column names
            template_columns = [
                str(col).strip().upper() for col in template_columns if str(col).strip()
            ]

            print("Template columns from URL:", template_columns)
            return template_columns

        except Exception as e:
            print(f"Error reading template from URL: {str(e)}")
        return None

    def process_item_data(self):
        try:
            self.upload_data_summary["model_type"] = "item"

            for index, row in self.df.iterrows():
                try:
                    item_data = {
                        "item_name": row["ITEM_NAME"],
                        "unit": row["UNIT"],
                        "category": row["CATEGORY"],
                        "category_step1": row["CATEGORY_STEP1"],
                        "quantity": row["QUANTITY"],
                        "unit_cost": row["UNIT_COST(UGX)"],
                        "unit_price": row["UNIT_PRICE(UGX)"],
                    }

                    with schema_context(self.request.tenant.schema_name):
                        item_name = row["ITEM_NAME"]
                        if (
                            self.models["item"]
                            .objects.filter(item_name__iexact=item_name)
                            .exists()
                        ):
                            existing_item = (
                                self.models["item"]
                                .objects.filter(item_name__iexact=item_name)
                                .first()
                            )

                            # Check if a journal entry with same characteristics exists
                            existing_journal = (
                                self.models["item journal"]
                                .objects.filter(
                                    item=existing_item,
                                    quantity=row["QUANTITY"],
                                    unit_cost=row["UNIT_COST(UGX)"],
                                    entry_type=self.enums[
                                        "entry type"
                                    ].PositiveAdjustment.name,
                                )
                                .first()
                            )

                            if existing_journal:
                                # Update existing journal entry
                                existing_journal.total = (
                                    row["QUANTITY"] * row["UNIT_COST(UGX)"]
                                )
                                existing_journal.unit_of_measure = row["UNIT"]
                                existing_journal.date = timezone.now()
                                existing_journal.user = self.request.user
                                existing_journal.save()

                                self.upload_data_summary["updated_records"] += 1
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "journal",
                                        "name": f"{item_name} - {row['QUANTITY']} units",
                                        "status": "updated",
                                    }
                                )
                            else:
                                # Create journal entry for existing item
                                journal_entry = self.models[
                                    "item journal"
                                ].objects.create(
                                    item=existing_item,
                                    quantity=row["QUANTITY"],
                                    entry_type=self.enums[
                                        "entry type"
                                    ].PositiveAdjustment.name,
                                    description="Initial stock upload",
                                    total=row["QUANTITY"] * row["UNIT_COST(UGX)"],
                                    unit_of_measure=row["UNIT"],
                                    unit_cost=row["UNIT_COST(UGX)"],
                                    date=timezone.now(),
                                    user=self.request.user,
                                )
                                self.upload_data_summary["created_records"] += 1
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "journal",
                                        "name": f"{item_name} - {row['QUANTITY']} units",
                                        "status": "created",
                                    }
                                )

                                self.upload_data_summary["updated_records"] += 1
                        else:
                            print("=============== item not found ================")
                            # Create parent category
                            parent_category, parent_created = self.models[
                                "item category"
                            ].objects.get_or_create(
                                description__iexact=row["CATEGORY"],
                                defaults={
                                    "description": row["CATEGORY"],
                                },
                            )
                            if parent_created:
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "category",
                                        "name": row["CATEGORY"],
                                        "status": "created",
                                    }
                                )

                            # Create child category
                            child_category, child_created = self.models[
                                "item category"
                            ].objects.get_or_create(
                                description__iexact=row["CATEGORY_STEP1"],
                                defaults={
                                    "description": row["CATEGORY_STEP1"],
                                    "parent": parent_category,
                                },
                            )
                            if child_created:
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "subcategory",
                                        "name": row["CATEGORY_STEP1"],
                                        "parent": row["CATEGORY"],
                                        "status": "created",
                                    }
                                )

                            # Create or get unit of measure
                            unit_of_measure, unit_created = self.models[
                                "unit of measure"
                            ].objects.get_or_create(
                                description__iexact=row["UNIT"],
                                international_stnd_code__iexact=row["UNIT"],
                                defaults={
                                    "description": row["UNIT"],
                                    "international_stnd_code": row["UNIT"],
                                },
                            )
                            if unit_created:
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "unit",
                                        "name": row["UNIT"],
                                        "status": "created",
                                    }
                                )

                            # Create new item
                            new_item = self.models["item"].objects.create(
                                item_name=item_name,
                                unit_of_measure=unit_of_measure,
                                description=item_name,
                                unit_price=row["UNIT_PRICE(UGX)"],
                                item_category=child_category,
                            )

                            # Create journal entry for new item
                            if new_item:
                                print(
                                    "=============== create journal entry ================"
                                )
                                journal_entry = self.models[
                                    "item journal"
                                ].objects.create(
                                    item=new_item,
                                    quantity=row["QUANTITY"],
                                    entry_type=self.enums[
                                        "entry type"
                                    ].PositiveAdjustment.name,
                                    description="Initial stock upload",
                                    total=row["QUANTITY"] * row["UNIT_COST(UGX)"],
                                    unit_of_measure=row["UNIT"],
                                    unit_cost=row["UNIT_COST(UGX)"],
                                    date=timezone.now(),
                                    user=self.request.user,
                                )
                                self.upload_data_summary["created_records"] += 1
                                self.upload_data_summary["details"].append(
                                    {
                                        "type": "item",
                                        "name": item_name,
                                        "category": row["CATEGORY"],
                                        "subcategory": row["CATEGORY_STEP1"],
                                        "unit": row["UNIT"],
                                        "status": "created",
                                    }
                                )

                    self.uploaded_data.append(item_data)
                    self.upload_data_summary["total_records"] += 1
                    self.upload_data_summary["url"] = reverse("items:items-list")

                except Exception as e:
                    self.upload_data_summary["failed_records"] += 1
                    self.upload_data_summary["details"].append(
                        {"type": "item", "name": item_name, "error": str(e)}
                    )
        except Exception as e:
            raise ValueError(f"Error processing item data: {str(e)}")

    def process_item_categories_data(self):
        try:
            self.upload_data_summary["model_type"] = "itemcategory"
            for index, row in self.df.iterrows():
                category = row["CATEGORY"].upper()
                subcategory = (
                    row["SUBCATEGORY"].upper() if pd.notna(row["SUBCATEGORY"]) else None
                )

                with schema_context(self.request.tenant.schema_name):
                    # First, get or create the parent category
                    parent_category, parent_created = self.models[
                        "item category"
                    ].objects.get_or_create(
                        description=category,
                        defaults={
                            "description": category,
                            "parent": None,  # This is a root category
                        },
                    )

                    if parent_created:
                        self.upload_data_summary["created_records"] += 1
                        self.upload_data_summary["details"].append(
                            {"type": "category", "name": category, "status": "created"}
                        )

                    # If subcategory exists, create it under the parent
                    if subcategory:
                        child_category, child_created = self.models[
                            "item category"
                        ].objects.get_or_create(
                            description=subcategory,
                            defaults={
                                "description": subcategory,
                                "parent": parent_category,
                            },
                        )

                        if child_created:
                            self.upload_data_summary["created_records"] += 1
                            self.upload_data_summary["details"].append(
                                {
                                    "type": "subcategory",
                                    "name": subcategory,
                                    "parent": category,
                                    "status": "created",
                                }
                            )

                    self.upload_data_summary["total_records"] += 1
                    self.upload_data_summary["url"] = reverse("items:items-list")

        except Exception as e:
            raise ValueError(f"Error processing item categories data: {str(e)}")

    def process_item_only_data(self):
        try:
            self.upload_data_summary["model_type"] = "itemsonly"
            for index, row in self.df.iterrows():
                item_data = {
                    "item_name": row["ITEM_NAME"].strip(),
                    "unit_of_measure": (
                        row["UNIT"].strip() if pd.notna(row["UNIT"]) else "PCS"
                    ),
                    "description": (
                        row["DESCRIPTION"].strip()
                        if pd.notna(row["DESCRIPTION"])
                        else row["ITEM_NAME"].strip()
                    ),
                    "category": (
                        row["CATEGORY"].strip().upper()
                        if pd.notna(row["CATEGORY"])
                        else "UNCATEGORIZED"
                    ),
                    "unit_price": (
                        row["UNIT_PRICE(UGX)"]
                        if pd.notna(row["UNIT_PRICE(UGX)"])
                        else 0
                    ),
                }

                with schema_context(self.request.tenant.schema_name):
                    # Check if category exists, if not create it
                    category, created = self.models[
                        "item category"
                    ].objects.get_or_create(
                        description=item_data["category"],
                        defaults={"description": item_data["category"], "parent": None},
                    )

                    # Get or create unit of measure
                    unit_of_measure, _ = self.models[
                        "unit of measure"
                    ].objects.get_or_create(
                        description=item_data["unit_of_measure"].upper(),
                        defaults={
                            "description": item_data["unit_of_measure"].upper(),
                            "international_stnd_code": item_data[
                                "unit_of_measure"
                            ].upper(),
                        },
                    )

                    # Create or update item
                    if (
                        self.models["item"]
                        .objects.filter(item_name=item_data["item_name"])
                        .exists()
                    ):

                        # update the item
                        item = self.models["item"].objects.get(
                            item_name=item_data["item_name"]
                        )
                        item.unit_of_measure = unit_of_measure
                        item.item_category = category
                        item.unit_price = item_data["unit_price"]
                        item.save()

                        self.upload_data_summary["updated_records"] += 1
                        self.upload_data_summary["details"].append(
                            {
                                "type": "item",
                                "name": item_data["item_name"],
                                "status": "updated",
                            }
                        )
                    else:
                        self.models["item"].objects.create(
                            item_name=item_data["item_name"],
                            description=item_data["description"],
                            unit_of_measure=unit_of_measure,
                            item_category=category,
                            unit_price=item_data["unit_price"],
                        )
                        self.upload_data_summary["created_records"] += 1
                        self.upload_data_summary["details"].append(
                            {
                                "type": "item",
                                "name": item_data["item_name"],
                                "status": "created",
                            }
                        )

                    self.upload_data_summary["total_records"] += 1
                    self.upload_data_summary["url"] = reverse("items:items-list")

        except Exception as e:
            raise ValueError(f"Error processing item only data: {str(e)}")

    def process_item_ledger_data(self):
        try:
            self.upload_data_summary["model_type"] = "itemledgerentries"
            for index, row in self.df.iterrows():
                item_ledger_data = {
                    "entry_type": row["ENTRY_TYPE"],
                    "description": row["DESCRIPTION"],
                    "quantity": row["QUANTITY"],
                    "unit_of_measure": row["UNIT"] if pd.notna(row["UNIT"]) else "PCS",
                    "remaining_quantity": row["REMAINING_QUANTITY"],
                    "total": row["TOTAL"],
                    "unit_cost": row["UNIT_COST"],
                    "unit_amount": row["UNIT_AMOUNT"],
                    "amount": row["AMOUNT"],
                    "item_name": row["ITEM_NAME"],
                    "document_no": row["DOCUMENT_NO"],
                    "date": row["DATE"] if pd.notna(row["DATE"]) else timezone.now(),
                }

                with schema_context(self.request.tenant.schema_name):
                    if (
                        not self.models["item"]
                        .objects.filter(item_name=item_ledger_data["item_name"])
                        .exists()
                    ):
                        self.upload_data_summary["failed_records"] += 1
                        self.upload_data_summary["details"].append(
                            {
                                "type": "item",
                                "name": item_ledger_data["item_name"],
                                "error": "Item not found",
                            }
                        )
                        continue

                    item = self.models["item"].objects.get(
                        item_name=item_ledger_data["item_name"]
                    )
                    uploaded_entry_type = row["ENTRY_TYPE"].strip()

                    # find the enum type value by name
                    try:
                        entry_type = getattr(
                            self.enums["entry type"], uploaded_entry_type
                        )
                    except ValueError:
                        raise ValueError(
                            f"Invalid entry type name: {uploaded_entry_type}"
                        )
                    self.models["item ledger entries"].objects.create(
                        item=item,
                        entry_type=entry_type.name,
                        description=item_ledger_data["description"],
                        quantity=item_ledger_data["quantity"],
                        unit_of_measure=item_ledger_data["unit_of_measure"],
                        remaining_quantity=item_ledger_data["remaining_quantity"],
                        total=item_ledger_data["total"],
                        unit_cost=item_ledger_data["unit_cost"],
                        unit_amount=item_ledger_data["unit_amount"],
                        amount=item_ledger_data["amount"],
                        date=item_ledger_data["date"],
                        user=self.request.user,
                        document_no=item_ledger_data["document_no"],
                    )
                    self.upload_data_summary["created_records"] += 1
                    self.upload_data_summary["details"].append(
                        {
                            "type": "item ledger",
                            "name": item_ledger_data["item_name"],
                            "status": "created",
                        }
                    )

                    self.upload_data_summary["total_records"] += 1
                    self.upload_data_summary["url"] = reverse("items:items-list")

        except Exception as e:
            raise ValueError(f"Error processing item ledger data: {str(e)}")

    def process_item_journal_data(self):
        try:
            self.upload_data_summary["model_type"] = "itemjournal"
            print("=============== process item journal data ================")
            for index, row in self.df.iterrows():

                item_journal_data = {
                    "item_name": row["ITEM_NAME"],
                    "quantity": row["QUANTITY"],
                    "unit_cost": row["UNIT_COST"],
                    "entry_type": row["ENTRY_TYPE"],
                    "description": row["DESCRIPTION"],
                    "unit_of_measure": row["UNIT"] if pd.notna(row["UNIT"]) else "PCS",
                    "total": row["TOTAL"],
                    "date": row["DATE"] if pd.notna(row["DATE"]) else timezone.now(),
                }
                try:
                    entry_type = getattr(
                        self.enums["entry type"], item_journal_data["entry_type"]
                    )
                except ValueError:
                    raise ValueError(
                        f"Invalid entry type name: {item_journal_data['entry_type']}"
                    )

                with schema_context(self.request.tenant.schema_name):
                    existing_item = self.models["item"].objects.get(
                        item_name=item_journal_data["item_name"]
                    )
                    if not existing_item:
                        raise ValueError(
                            f"Item not found Please first create the item: {item_journal_data['item_name']}"
                        )
                    # Check if a journal entry with same characteristics exists
                    existing_journal = (
                        self.models["item journal"]
                        .objects.filter(
                            item=existing_item,
                            quantity=item_journal_data["quantity"],
                            unit_cost=item_journal_data["unit_cost"],
                            entry_type=entry_type.name,
                        )
                        .first()
                    )

                    if existing_journal:
                        existing_journal.total = item_journal_data["total"]
                        existing_journal.unit_of_measure = item_journal_data[
                            "unit_of_measure"
                        ]
                        existing_journal.date = item_journal_data["date"]
                        existing_journal.user = self.request.user
                        existing_journal.save()
                        self.upload_data_summary["updated_records"] += 1
                        self.upload_data_summary["details"].append(
                            {
                                "type": "journal",
                                "name": f"{item_journal_data['item_name']} - {item_journal_data['quantity']} units",
                                "status": "updated",
                            }
                        )
                    else:
                        self.models["item journal"].objects.create(
                            item=existing_item,
                            quantity=item_journal_data["quantity"],
                            unit_cost=item_journal_data["unit_cost"],
                            entry_type=entry_type.name,
                            description=item_journal_data["description"],
                            unit_of_measure=self.models[
                                "unit of measure"
                            ].objects.get_or_create(
                                description=item_journal_data["unit_of_measure"],
                                defaults={
                                    "description": item_journal_data["unit_of_measure"],
                                    "international_stnd_code": item_journal_data[
                                        "unit_of_measure"
                                    ],
                                },
                            ),
                            total=item_journal_data["total"],
                            date=item_journal_data["date"],
                            user=self.request.user,
                        )
                        self.upload_data_summary["created_records"] += 1
                        self.upload_data_summary["details"].append(
                            {
                                "type": "journal",
                                "name": f"{item_journal_data['item_name']} - {item_journal_data['quantity']} units",
                                "status": "created",
                            }
                        )
                    self.upload_data_summary["url"] = reverse("items:item-journal")
                    self.upload_data_summary["total_records"] += 1

        except Exception as e:
            raise ValueError(f"Error processing item journal data: {str(e)}")
