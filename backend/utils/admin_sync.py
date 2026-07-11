"""
Admin Sync Utilities
Provides reusable admin actions for syncing data from JSON export files.
"""

import json
import os
from django.contrib import admin, messages
from django.conf import settings


def get_model_from_path(model_path):
    """
    Convert model path like 'financials.G_LAccount' to actual model class.

    Args:
        model_path: String like 'app.ModelName'

    Returns:
        Model class or None if not found
    """
    from django.apps import apps

    try:
        app_label, model_name = model_path.split(".")
        return apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        return None


def sync_from_json_file(modeladmin, request, queryset, json_file_path=None):
    """
    Sync data from JSON export file to database.
    Updates existing records or creates new ones.

    Args:
        modeladmin: The ModelAdmin instance
        request: The HttpRequest
        queryset: Selected queryset (not used, but required for admin actions)
        json_file_path: Optional path to JSON file. If None, uses default export file.
    """
    # Default to the tenant export file in the project root
    if json_file_path is None:
        json_file_path = os.path.join(
            settings.BASE_DIR, "tenant_semuna_export_20250227_062346.json"
        )

    # Check if file exists
    if not os.path.exists(json_file_path):
        modeladmin.message_user(
            request, f"JSON file not found: {json_file_path}", level=messages.ERROR
        )
        return

    try:
        # Read JSON file
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Get the model key for this admin's model
        model = modeladmin.model
        app_label = model._meta.app_label
        model_name = model._meta.object_name
        model_key = f"{app_label}.{model_name}"

        # Check if data exists for this model
        if model_key not in data.get("data", {}):
            modeladmin.message_user(
                request,
                f"No data found for {model_key} in JSON file",
                level=messages.WARNING,
            )
            return

        records = data["data"][model_key]
        created_count = 0
        updated_count = 0
        error_count = 0

        # Debug: Log the model name
        modeladmin.message_user(
            request, f"Processing model: {model.__name__}", level=messages.INFO
        )

        # Process each record
        for record_data in records:
            try:
                # Debug: Log GeneralPostingSetup records
                if model.__name__ == "GeneralPostingSetup":
                    modeladmin.message_user(
                        request,
                        f"Processing GeneralPostingSetup record: {record_data}",
                        level=messages.INFO,
                    )

                # Determine unique fields for lookup (usually 'code' or 'no')
                lookup_field = None
                lookup_value = None

                # Special handling for GeneralPostingSetup - match by combination of fields
                if model.__name__ == "GeneralPostingSetup":
                    # Debug: Log that we're processing GeneralPostingSetup
                    modeladmin.message_user(
                        request,
                        f"Processing GeneralPostingSetup record: {record_data}",
                        level=messages.INFO,
                    )
                    # Try to find existing record by product and business posting groups
                    try:
                        existing_obj = None
                        if record_data.get(
                            "general_product_posting_group"
                        ) and record_data.get("general_business_posting_group"):
                            existing_obj = model.objects.filter(
                                general_product_posting_group__code=record_data[
                                    "general_product_posting_group"
                                ],
                                general_business_posting_group__code=record_data[
                                    "general_business_posting_group"
                                ],
                            ).first()
                        elif record_data.get("general_product_posting_group"):
                            existing_obj = model.objects.filter(
                                general_product_posting_group__code=record_data[
                                    "general_product_posting_group"
                                ],
                                general_business_posting_group__isnull=True,
                            ).first()

                        if existing_obj:
                            # Update existing record
                            for field_name, field_value in record_data.items():
                                if field_name in [
                                    "id",
                                    "system_id",
                                    "created_at",
                                    "updated_at",
                                ]:
                                    continue
                                # Handle foreign key fields
                                if isinstance(field_value, str) and any(
                                    field_name.endswith(suffix)
                                    for suffix in ["_account", "_group", "_no"]
                                ):
                                    field_obj = model._meta.get_field(field_name)
                                    if field_obj.is_relation:
                                        related_model = field_obj.related_model
                                        try:
                                            related_obj = None
                                            for lookup in ["name", "code", "no"]:
                                                try:
                                                    related_obj = (
                                                        related_model.objects.get(
                                                            **{lookup: field_value}
                                                        )
                                                    )
                                                    break
                                                except related_model.DoesNotExist:
                                                    continue
                                            if related_obj:
                                                setattr(
                                                    existing_obj,
                                                    field_name,
                                                    related_obj,
                                                )
                                        except Exception:
                                            pass
                                else:
                                    setattr(existing_obj, field_name, field_value)

                            existing_obj.save()
                            updated_count += 1
                        else:
                            # Create new record
                            new_obj = model()
                            for field_name, field_value in record_data.items():
                                if field_name in [
                                    "id",
                                    "system_id",
                                    "created_at",
                                    "updated_at",
                                ]:
                                    continue
                                # Handle foreign key fields
                                if isinstance(field_value, str) and any(
                                    field_name.endswith(suffix)
                                    for suffix in ["_account", "_group", "_no"]
                                ):
                                    field_obj = model._meta.get_field(field_name)
                                    if field_obj.is_relation:
                                        related_model = field_obj.related_model
                                        try:
                                            related_obj = None
                                            for lookup in ["name", "code", "no"]:
                                                try:
                                                    related_obj = (
                                                        related_model.objects.get(
                                                            **{lookup: field_value}
                                                        )
                                                    )
                                                    break
                                                except related_model.DoesNotExist:
                                                    continue
                                            if related_obj:
                                                setattr(
                                                    new_obj, field_name, related_obj
                                                )
                                        except Exception:
                                            pass
                                else:
                                    setattr(new_obj, field_name, field_value)

                            new_obj.save()
                            created_count += 1

                        continue  # Skip the normal processing for GeneralPostingSetup
                    except Exception as e:
                        error_count += 1
                        modeladmin.message_user(
                            request,
                            f"Error processing GeneralPostingSetup record: {str(e)}",
                            level=messages.ERROR,
                        )
                        continue

                if "code" in record_data:
                    lookup_field = "code"
                    lookup_value = record_data["code"]
                elif "no" in record_data:
                    lookup_field = "no"
                    lookup_value = record_data["no"]
                else:
                    # For models without code/no, try to find a unique field
                    for field in ["name", "id"]:
                        if field in record_data:
                            lookup_field = field
                            lookup_value = record_data[field]
                            break

                if lookup_field and lookup_value:
                    # Handle foreign key fields
                    processed_data = {}
                    for field_name, field_value in record_data.items():
                        # Check if this is a foreign key field (ends with _account, _group, etc.)
                        if isinstance(field_value, str) and any(
                            field_name.endswith(suffix)
                            for suffix in ["_account", "_group", "_no"]
                        ):
                            # Try to resolve foreign key by name/code/no
                            field_obj = model._meta.get_field(field_name)
                            if field_obj.is_relation:
                                related_model = field_obj.related_model
                                try:
                                    # Try to find related object by various fields
                                    related_obj = None
                                    for lookup in ["name", "code", "no"]:
                                        try:
                                            related_obj = related_model.objects.get(
                                                **{lookup: field_value}
                                            )
                                            break
                                        except (
                                            related_model.DoesNotExist,
                                            related_model.MultipleObjectsReturned,
                                        ):
                                            continue

                                    if related_obj:
                                        processed_data[field_name] = related_obj
                                    else:
                                        # Keep original value if can't resolve
                                        processed_data[field_name] = field_value
                                except Exception:
                                    processed_data[field_name] = field_value
                            else:
                                processed_data[field_name] = field_value
                        else:
                            processed_data[field_name] = field_value

                    # Use update_or_create
                    obj, created = model.objects.update_or_create(
                        **{lookup_field: lookup_value}, defaults=processed_data
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                modeladmin.message_user(
                    request, f"Error processing record: {str(e)}", level=messages.ERROR
                )

        # Show success message
        message = f"Sync completed: {created_count} created, {updated_count} updated"
        if error_count > 0:
            message += f", {error_count} errors"

        modeladmin.message_user(
            request,
            message,
            level=messages.SUCCESS if error_count == 0 else messages.WARNING,
        )

    except Exception as e:
        modeladmin.message_user(
            request, f"Error reading JSON file: {str(e)}", level=messages.ERROR
        )


def sync_all_models_from_json(modeladmin, request, queryset, json_file_path=None):
    """
    Sync ALL models from JSON export file to database.
    This is a global sync action that processes all model data in the file.

    Args:
        modeladmin: The ModelAdmin instance
        request: The HttpRequest
        queryset: Selected queryset (not used)
        json_file_path: Optional path to JSON file
    """
    # Default to the tenant export file
    if json_file_path is None:
        json_file_path = os.path.join(
            settings.BASE_DIR, "tenant_semuna_export_20250227_062346.json"
        )

    if not os.path.exists(json_file_path):
        modeladmin.message_user(
            request, f"JSON file not found: {json_file_path}", level=messages.ERROR
        )
        return

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_created = 0
        total_updated = 0
        total_errors = 0
        processed_models = []

        # Process each model in the JSON data
        for model_path, records in data.get("data", {}).items():
            try:
                model = get_model_from_path(model_path)
                if not model:
                    modeladmin.message_user(
                        request,
                        f"Model not found: {model_path}",
                        level=messages.WARNING,
                    )
                    continue

                # Debug: Log which model we're processing
                modeladmin.message_user(
                    request,
                    f"Processing model: {model_path} ({model.__name__})",
                    level=messages.INFO,
                )

                created_count = 0
                updated_count = 0

                for record_data in records:
                    try:
                        # Debug: Log GeneralPostingSetup records
                        if model.__name__ == "GeneralPostingSetup":
                            modeladmin.message_user(
                                request,
                                f"Processing GeneralPostingSetup record: {record_data}",
                                level=messages.INFO,
                            )

                        # Special handling for GeneralPostingSetup - match by combination of fields
                        if model.__name__ == "GeneralPostingSetup":
                            # Try to find existing record by product and business posting groups
                            try:
                                existing_obj = None
                                if record_data.get(
                                    "general_product_posting_group"
                                ) and record_data.get("general_business_posting_group"):
                                    existing_obj = model.objects.filter(
                                        general_product_posting_group__code=record_data[
                                            "general_product_posting_group"
                                        ],
                                        general_business_posting_group__code=record_data[
                                            "general_business_posting_group"
                                        ],
                                    ).first()
                                elif record_data.get("general_product_posting_group"):
                                    existing_obj = model.objects.filter(
                                        general_product_posting_group__code=record_data[
                                            "general_product_posting_group"
                                        ],
                                        general_business_posting_group__isnull=True,
                                    ).first()

                                if existing_obj:
                                    # Update existing record
                                    for field_name, field_value in record_data.items():
                                        if field_name in [
                                            "id",
                                            "system_id",
                                            "created_at",
                                            "updated_at",
                                        ]:
                                            continue
                                        # Handle foreign key fields
                                        if isinstance(field_value, str) and any(
                                            field_name.endswith(suffix)
                                            for suffix in ["_account", "_group", "_no"]
                                        ):
                                            field_obj = model._meta.get_field(
                                                field_name
                                            )
                                            if field_obj.is_relation:
                                                related_model = field_obj.related_model
                                                try:
                                                    related_obj = None
                                                    for lookup in [
                                                        "name",
                                                        "no",
                                                        "code",
                                                    ]:
                                                        try:
                                                            related_obj = related_model.objects.get(
                                                                **{lookup: field_value}
                                                            )
                                                            break
                                                        except (
                                                            related_model.DoesNotExist
                                                        ):
                                                            continue
                                                    if related_obj:
                                                        setattr(
                                                            existing_obj,
                                                            field_name,
                                                            related_obj,
                                                        )
                                                except Exception:
                                                    pass
                                        else:
                                            setattr(
                                                existing_obj, field_name, field_value
                                            )

                                    existing_obj.save()
                                    updated_count += 1
                                else:
                                    # Create new record
                                    new_obj = model()
                                    for field_name, field_value in record_data.items():
                                        if field_name in [
                                            "id",
                                            "system_id",
                                            "created_at",
                                            "updated_at",
                                        ]:
                                            continue
                                        # Handle foreign key fields
                                        if isinstance(field_value, str) and any(
                                            field_name.endswith(suffix)
                                            for suffix in ["_account", "_group", "_no"]
                                        ):
                                            field_obj = model._meta.get_field(
                                                field_name
                                            )
                                            if field_obj.is_relation:
                                                related_model = field_obj.related_model
                                                try:
                                                    related_obj = None
                                                    for lookup in [
                                                        "name",
                                                        "no",
                                                        "code",
                                                    ]:
                                                        try:
                                                            related_obj = related_model.objects.get(
                                                                **{lookup: field_value}
                                                            )
                                                            break
                                                        except (
                                                            related_model.DoesNotExist
                                                        ):
                                                            continue
                                                    if related_obj:
                                                        setattr(
                                                            new_obj,
                                                            field_name,
                                                            related_obj,
                                                        )
                                                        modeladmin.message_user(
                                                            request,
                                                            f"Found related object for {field_name}: {related_obj}",
                                                            level=messages.INFO,
                                                        )
                                                    else:
                                                        modeladmin.message_user(
                                                            request,
                                                            f"Could not find related object for {field_name}: {field_value}",
                                                            level=messages.WARNING,
                                                        )
                                                except Exception as e:
                                                    modeladmin.message_user(
                                                        request,
                                                        f"Error resolving {field_name}: {str(e)}",
                                                        level=messages.ERROR,
                                                    )
                                        else:
                                            setattr(new_obj, field_name, field_value)

                                    # Debug: Log the object before saving
                                    modeladmin.message_user(
                                        request,
                                        f"About to save GeneralPostingSetup: product_group={new_obj.general_product_posting_group}, business_group={new_obj.general_business_posting_group}",
                                        level=messages.INFO,
                                    )

                                    new_obj.save()
                                    created_count += 1

                                continue  # Skip the normal processing for GeneralPostingSetup
                            except Exception as e:
                                modeladmin.message_user(
                                    request,
                                    f"Error processing GeneralPostingSetup record: {str(e)}",
                                    level=messages.ERROR,
                                )
                                continue

                        # Determine lookup field
                        lookup_field = None
                        lookup_value = None

                        for field in ["code", "no", "name"]:
                            if field in record_data:
                                lookup_field = field
                                lookup_value = record_data[field]
                                break

                        if lookup_field and lookup_value:
                            # Handle foreign keys
                            processed_data = {}
                            for field_name, field_value in record_data.items():
                                try:
                                    field_obj = model._meta.get_field(field_name)
                                    if field_obj.is_relation and isinstance(
                                        field_value, str
                                    ):
                                        related_model = field_obj.related_model
                                        related_obj = None
                                        for lookup in ["name", "code", "no"]:
                                            try:
                                                related_obj = related_model.objects.get(
                                                    **{lookup: field_value}
                                                )
                                                break
                                            except:
                                                continue
                                        processed_data[field_name] = (
                                            related_obj if related_obj else field_value
                                        )
                                    else:
                                        processed_data[field_name] = field_value
                                except:
                                    processed_data[field_name] = field_value

                            obj, created = model.objects.update_or_create(
                                **{lookup_field: lookup_value}, defaults=processed_data
                            )

                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                    except Exception as e:
                        total_errors += 1

                total_created += created_count
                total_updated += updated_count
                processed_models.append(
                    f"{model_path}: {created_count} created, {updated_count} updated"
                )

            except Exception as e:
                modeladmin.message_user(
                    request,
                    f"Error processing {model_path}: {str(e)}",
                    level=messages.ERROR,
                )

        # Show summary
        summary = f"Global sync completed:\n"
        summary += f"Total: {total_created} created, {total_updated} updated"
        if total_errors > 0:
            summary += f", {total_errors} errors"
        summary += f"\n\nProcessed models:\n" + "\n".join(processed_models)

        modeladmin.message_user(
            request,
            summary,
            level=messages.SUCCESS if total_errors == 0 else messages.WARNING,
        )

    except Exception as e:
        modeladmin.message_user(request, f"Error: {str(e)}", level=messages.ERROR)


# Configure action properties
sync_from_json_file.short_description = "🔄 Sync from JSON file (this model only)"
sync_all_models_from_json.short_description = "🔄 Sync ALL models from JSON file"
