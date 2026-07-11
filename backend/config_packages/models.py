from django.db import models
from utils.utils import BaseModel
from django.apps import apps
from django.utils.functional import lazy
import uuid


# class ConfigPackage(models.Model):
#     """
#     Configuration Package model
#     """

#     class ImportApplyStatus(models.TextChoices):
#         NO = "NO", "No"
#         SCHEDULED = "SCHEDULED", "Scheduled"
#         IN_PROGRESS = "IN_PROGRESS", "InProgress"
#         COMPLETED = "COMPLETED", "Completed"
#         ERROR = "ERROR", "Error"

#     # Primary identifier
#     code = models.CharField(
#         max_length=20, primary_key=True, help_text="Configuration package identifier"
#     )

#     # Basic fields
#     package_name = models.CharField(max_length=50)


# class ConfigPackageTable(models.Model):
#     """
#     Configuration Package Table model based on NAV/Business Central table 8613
#     """
#     # Foreign key to Config Package
#     package_code = models.ForeignKey(
#         'config_packages.ConfigPackage',
#         on_delete=models.CASCADE,
#         db_column='package_code'
#     )

#     # Basic fields
#     table_id = models.IntegerField(

#     )

#     # validators=[MinValueValidator(1)],
#     # help_text="Table ID from Business Central"


def get_model_choices():
    """
    Returns a list of tuples for model choices
    """
    choices = [
        # custom choices
        ("itemsonly", "Items Only"),
    ]
    for model in apps.get_models():
        # Skip Django's built-in models
        if model._meta.app_label in [
            "admin",
            "auth",
            "contenttypes",
            "sessions",
            "messages",
        ]:
            continue

        # Skip abstract models
        if model._meta.abstract:
            continue

        # Create choice tuple (value, display_name)
        choice = (
            model._meta.model_name,
            # f"{model._meta.verbose_name.title()} ({model._meta.app_label})"
            f"{model._meta.verbose_name.title()}",
        )
        choices.append(choice)

    return sorted(choices, key=lambda x: x[1])


# Create lazy choices to avoid apps registry error
get_model_choices_lazy = lazy(get_model_choices, list)


class UploadTemplates(BaseModel):
    """
    Upload Templates model
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Name of the upload template",
        # choices=get_model_choices_lazy(),  # Use lazy evaluation
    )

    template_file = models.FileField(
        upload_to="upload_templates/", help_text="File of the upload template"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set choices dynamically only when instance is created
        self._meta.get_field("name").choices = get_model_choices_lazy()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Upload Template"
        verbose_name_plural = "Upload Templates"
        ordering = ["name"]

    # @classmethod
    # def get_model_info(cls, model_name):
    #     """
    #     Get detailed information about a specific model
    #     """
    #     for model in apps.get_models():
    #         if model._meta.model_name == model_name:
    #             return {
    #                 "name": model._meta.verbose_name.title(),
    #                 "app_label": model._meta.app_label,
    #                 "table_name": model._meta.db_table,
    #                 "fields": [
    #                     {
    #                         "name": field.name,
    #                         "type": field.get_internal_type(),
    #                         "required": not field.null and not field.blank,
    #                         "help_text": field.help_text,
    #                     }
    #                     for field in model._meta.fields
    #                 ],
    #             }
    #     return None


class ConfigPackage(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        VALIDATED = "VALIDATED", "Validated"
        APPLIED = "APPLIED", "Applied"
        ERROR = "ERROR", "Error"

    code = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="Configuration package identifier",
        unique=True,
    )
    package_name = models.CharField(
        max_length=100, help_text="Name of the configuration package"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    # class Meta:
    #     db_table = "ConfigPackage"


class ConfigPackageTable(BaseModel):
    """
    Configuration Package Table model
    """

    package_code = models.ForeignKey(
        "ConfigPackage",
        on_delete=models.CASCADE,
        db_column="package_code",
    )
    table_id = models.ForeignKey(
        "base.Objects",
        on_delete=models.CASCADE,
        help_text="Reference to the table object",
        limit_choices_to={"object_type": "Table"},
    )
    table_name = models.CharField(max_length=100, help_text="Name of the table")
    description = models.TextField(
        blank=True, null=True, help_text="Description of the table configuration"
    )
    data = models.JSONField(default=list)  # Stores the table data
    field_config = models.JSONField(
        default=dict,
        help_text="Field export configuration including primary, default, and custom fields",
    )

    class Meta:
        unique_together = ("package_code", "table_id")

    def save(self, *args, **kwargs):
        # Auto-populate field_config if it's empty or table_name has changed
        if not self.field_config or "fields" not in self.field_config:
            self.populate_field_config()
        super().save(*args, **kwargs)

    def populate_field_config(self):
        """
        Automatically populate field configuration based on the table model
        """
        try:
            # Get the model class
            model = None
            print(
                f"DEBUG: populate_field_config called for table_name: {self.table_name}"
            )

            # First try to find the model using the table_name as is
            for app_config in apps.get_app_configs():
                try:
                    model = apps.get_model(app_config.label, self.table_name)
                    print(f"DEBUG: Found model using table_name as is: {model}")
                    break
                except LookupError:
                    continue

            # If not found, try to convert snake_case to camelCase
            if not model:
                # Convert snake_case to camelCase (e.g., item_journal -> ItemJournal)
                # First try with underscore split
                camel_case_name = "".join(
                    word.capitalize() for word in self.table_name.split("_")
                )
                print(f"DEBUG: Trying camel_case_name (underscore): {camel_case_name}")
                for app_config in apps.get_app_configs():
                    try:
                        model = apps.get_model(app_config.label, camel_case_name)
                        print(f"DEBUG: Found model using camel_case_name: {model}")
                        break
                    except LookupError:
                        continue

                # If still not found, try with space split
                if not model:
                    camel_case_name = "".join(
                        word.capitalize() for word in self.table_name.split(" ")
                    )
                    print(f"DEBUG: Trying camel_case_name (space): {camel_case_name}")
                    for app_config in apps.get_app_configs():
                        try:
                            model = apps.get_model(app_config.label, camel_case_name)
                            print(f"DEBUG: Found model using camel_case_name: {model}")
                            break
                        except LookupError:
                            continue

            if not model:
                # If model not found, set default empty config but preserve custom fields
                print(f"DEBUG: No model found for table_name: {self.table_name}")
                existing_custom_fields = (
                    self.field_config.get("custom_fields", [])
                    if self.field_config
                    else []
                )
                self.field_config = {
                    "primary_fields": [],
                    "default_fields": [],
                    "custom_fields": existing_custom_fields,  # Preserve existing custom fields
                    "excluded_fields": [],
                    "fields": [],
                }
                return

            # Get all fields from the model
            all_fields = []
            primary_fields = []
            default_fields = []
            excluded_fields = []

            # User's default export fields for the item table
            item_default_fields = [
                "no",
                "item_name",
                "bar_code_no",
                "shelf_no",
                "unit_price",
                "description",
                "unit_of_measure",
                "purchase_unit_of_measure",
                "sales_unit_of_measure",
                "item_category",
            ]

            # User's default export fields for the item_journal table
            item_journal_default_fields = [
                "document_no",
                "item",
                "entry_type",
                "description",
                "quantity",
                "item_unit_of_measure",
                "unit_amount",
                "amount",
                "unit_cost",
                "location_code",
                "date",
                "user",
                "status",
            ]

            # User's default export fields for the tracking_specification table
            tracking_specification_default_fields = [
                "item",
                "location_code",
                "lot_no",
                "serial_no",
                "expiry_date",
                "quantity_base",
                "description",
                "item_journal",
            ]

            print(
                f"DEBUG: Processing {len(model._meta.get_fields())} fields for model {model}"
            )
            for field in model._meta.get_fields():
                field_info = {
                    "name": field.name,
                    "verbose_name": getattr(field, "verbose_name", field.name),
                    "type": field.get_internal_type(),
                    "is_relation": field.is_relation,
                    "null": getattr(field, "null", False),
                    "blank": getattr(field, "blank", False),
                    "help_text": getattr(field, "help_text", ""),
                }

                # Set as default if in your list for item table
                if (
                    self.table_name.lower() == "item"
                    and field.name in item_default_fields
                ):
                    default_fields.append(field.name)
                    field_info["is_default"] = True
                elif (
                    self.table_name.lower() == "item_journal"
                    and field.name in item_journal_default_fields
                ):
                    default_fields.append(field.name)
                    field_info["is_default"] = True
                elif (
                    self.table_name.lower() == "tracking_specification"
                    and field.name in tracking_specification_default_fields
                ):
                    default_fields.append(field.name)
                    field_info["is_default"] = True
                else:
                    field_info["is_default"] = False

                # You can keep your primary/excluded logic as before
                if field.name in [
                    "id",
                    "no",
                    "code",
                    "name",
                    "email",
                    "document_no",
                    "lot_no",
                ]:
                    primary_fields.append(field.name)
                    field_info["is_primary"] = True
                elif field.name in [
                    "created_at",
                    "updated_at",
                    "system_id",
                    "password",
                    "last_login",
                ]:
                    excluded_fields.append(field.name)
                    field_info["is_excluded"] = True
                else:
                    field_info["is_primary"] = False
                    field_info["is_excluded"] = False

                all_fields.append(field_info)

            # Preserve existing custom_fields if they exist
            existing_custom_fields = (
                self.field_config.get("custom_fields", []) if self.field_config else []
            )

            self.field_config = {
                "primary_fields": primary_fields,
                "default_fields": default_fields,
                "custom_fields": existing_custom_fields,  # Preserve existing custom fields
                "excluded_fields": excluded_fields,
                "fields": all_fields,
            }

        except Exception as e:
            # If there's an error, set default empty config but preserve custom fields
            existing_custom_fields = (
                self.field_config.get("custom_fields", []) if self.field_config else []
            )
            self.field_config = {
                "primary_fields": [],
                "default_fields": [],
                "custom_fields": existing_custom_fields,  # Preserve existing custom fields
                "excluded_fields": [],
                "fields": [],
            }

    def get_export_fields(self):
        """
        Get the list of fields that should be included in exports
        """
        if not self.field_config:
            self.populate_field_config()

        # Combine primary fields, default fields, and custom fields
        # Exclude any fields that are in excluded_fields
        export_fields = []

        # Add primary fields (always included)
        export_fields.extend(self.field_config.get("primary_fields", []))

        # Add default fields (included by default)
        export_fields.extend(self.field_config.get("default_fields", []))

        # Add custom fields (user additions)
        export_fields.extend(self.field_config.get("custom_fields", []))

        # Remove excluded fields
        excluded = set(self.field_config.get("excluded_fields", []))
        export_fields = [field for field in export_fields if field not in excluded]

        return list(set(export_fields))  # Remove duplicates

    def update_field_config(
        self,
        primary_fields=None,
        default_fields=None,
        custom_fields=None,
        excluded_fields=None,
    ):
        """
        Update the field configuration
        """
        if primary_fields is not None:
            self.field_config["primary_fields"] = primary_fields
        if default_fields is not None:
            self.field_config["default_fields"] = default_fields
        if custom_fields is not None:
            self.field_config["custom_fields"] = custom_fields
        if excluded_fields is not None:
            self.field_config["excluded_fields"] = excluded_fields

        self.save()
