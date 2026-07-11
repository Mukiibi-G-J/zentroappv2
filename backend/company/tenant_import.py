"""
Programmatic tenant JSON import (shared by management command and Celery).
"""

from django.apps import apps
from django.db import connection, transaction


def run_tenant_data_import(schema_name, data, stdout, stderr, style):
    """
    Import tenant payload dict into schema_name. Caller must supply stdout/stderr/style
    (e.g. from BaseCommand or OutputWrapper + color_style for Celery).
    """
    try:
        with transaction.atomic():
            connection.set_schema(schema_name)

            model_relationships = {
                "financials.PaymentMethod": {
                    "bal_account_no": ("financials.G_LAccount", "name"),
                    "bal_bank_account_no": (
                        "bank_account.BankAccount",
                        "no",
                    ),
                },
                "sales.CustomerPostingGroup": {
                    "receivables_account": ("financials.G_LAccount", "name")
                },
                "sales.Customer": {
                    "customer_posting_group": (
                        "sales.CustomerPostingGroup",
                        "code",
                    ),
                    "general_business_posting_group": (
                        "postings.GeneralBusinessPostingGroup",
                        "code",
                    ),
                    "payment_method": ("financials.PaymentMethod", "code"),
                },
                "postings.GeneralPostingSetup": {
                    "general_product_posting_group": (
                        "postings.GeneralProductPostingGroup",
                        "code",
                    ),
                    "general_business_posting_group": (
                        "postings.GeneralBusinessPostingGroup",
                        "code",
                    ),
                    "sales_account": ("financials.G_LAccount", "name"),
                    "purchase_account": ("financials.G_LAccount", "name"),
                    "cogs_account": ("financials.G_LAccount", "name"),
                    "inventory_adjustment_account": (
                        "financials.G_LAccount",
                        "name",
                    ),
                    "direct_cost_applied_account": (
                        "financials.G_LAccount",
                        "name",
                    ),
                    "prepayment_account": (
                        "financials.G_LAccount",
                        "name",
                    ),
                    "sales_line_discount_account": (
                        "financials.G_LAccount",
                        "name",
                    ),
                },
                "postings.InventoryPostingSetup": {
                    "inventory_posting_group": (
                        "postings.InventoryPostingGroup",
                        "code",
                    ),
                    "inventory_account": ("financials.G_LAccount", "name"),
                    "wip_account": ("financials.G_LAccount", "name"),
                    "location": (
                        "items.Location",
                        "code",
                    ),
                },
                "purchases.VendorPostingGroup": {
                    "payables_account": ("financials.G_LAccount", "name"),
                },
                "purchases.Vendor": {
                    "vendor_posting_group": (
                        "purchases.VendorPostingGroup",
                        "code",
                    ),
                    "business_posting_group": (
                        "postings.GeneralBusinessPostingGroup",
                        "code",
                    ),
                    "payment_method": ("financials.PaymentMethod", "code"),
                },
                "bank_account.BankAccountPostingGroup": {
                    "bank_account": ("financials.G_LAccount", "name"),
                },
                "bank_account.BankAccount": {
                    "bank_account_posting_group": (
                        "bank_account.BankAccountPostingGroup",
                        "code",
                    ),
                },
            }

            model_order = [
                "financials.G_LAccount",
                "postings.GeneralProductPostingGroup",
                "postings.GeneralBusinessPostingGroup",
                "postings.InventoryPostingGroup",
                "postings.InventoryPostingSetup",
                "bank_account.BankAccountPostingGroup",
                "bank_account.BankAccount",
                "financials.PaymentMethod",
                "sales.CustomerPostingGroup",
                "sales.Customer",
                "postings.GeneralPostingSetup",
                "items.UnitOfMeasure",
                "purchases.VendorPostingGroup",
            ]

            for model_name in model_order:
                if model_name in data["data"]:
                    records = data["data"][model_name]
                    if not records:
                        continue

                    app_label, model = model_name.split(".")
                    Model = apps.get_model(app_label, model)

                    for record in records.copy():
                        try:
                            if model_name in model_relationships:
                                for field_name, (
                                    related_model_name,
                                    lookup_field,
                                ) in model_relationships[model_name].items():
                                    if field_name in record and record[field_name]:
                                        try:
                                            related_app, related_model = (
                                                related_model_name.split(".")
                                            )
                                            RelatedModel = apps.get_model(
                                                related_app, related_model
                                            )
                                            lookup_value = record[field_name]

                                            if isinstance(lookup_value, dict):
                                                lookup_value = (
                                                    lookup_value.get("code")
                                                    or lookup_value.get("id")
                                                    or lookup_value.get("pk")
                                                    or lookup_value.get("value")
                                                )

                                            if (
                                                related_model_name
                                                == "items.Location"
                                                and not lookup_value
                                            ):
                                                record.pop(field_name, None)
                                                continue

                                            lookup_kwargs = {
                                                lookup_field: lookup_value
                                            }
                                            try:
                                                related_obj = (
                                                    RelatedModel.objects.get(
                                                        **lookup_kwargs
                                                    )
                                                )
                                            except RelatedModel.DoesNotExist:
                                                if (
                                                    related_model_name
                                                    == "items.Location"
                                                ):
                                                    lookup_value_str = (
                                                        str(lookup_value).strip()
                                                        if lookup_value
                                                        else ""
                                                    )
                                                    if not lookup_value_str:
                                                        record.pop(field_name, None)
                                                        continue
                                                    related_obj, _ = (
                                                        RelatedModel.objects.get_or_create(
                                                            code=lookup_value_str,
                                                            defaults={
                                                                "description": lookup_value_str,
                                                                "address": lookup_value_str,
                                                            },
                                                        )
                                                    )
                                                else:
                                                    raise
                                            record[field_name] = related_obj

                                            stdout.write(
                                                style.SUCCESS(
                                                    f"Resolved relationship for {field_name} in {model_name}"
                                                )
                                            )
                                        except Exception as e:
                                            stdout.write(
                                                style.ERROR(
                                                    f"Error resolving relationship for {field_name} in {model_name}: {str(e)}"
                                                )
                                            )
                                            raise

                            models_with_get_or_create = {
                                "bank_account.BankAccount": "no",
                                "bank_account.BankAccountPostingGroup": "code",
                                "financials.G_LAccount": "no",
                                "financials.PaymentMethod": "code",
                            }

                            record.pop("id", None)
                            record.pop("system_id", None)

                            if model_name in models_with_get_or_create:
                                unique_field = models_with_get_or_create[model_name]
                                if unique_field in record:
                                    obj, created = Model.objects.get_or_create(
                                        **{unique_field: record[unique_field]},
                                        defaults=record,
                                    )
                                    if created:
                                        stdout.write(
                                            style.SUCCESS(
                                                f"Created {model_name} record: {record.get(unique_field)}"
                                            )
                                        )
                                    else:
                                        stdout.write(
                                            style.WARNING(
                                                f"Found existing {model_name} record: {record.get(unique_field)} (skipped)"
                                            )
                                        )
                                else:
                                    Model.objects.create(**record)
                                    stdout.write(
                                        style.SUCCESS(
                                            f"Created {model_name} record successfully"
                                        )
                                    )
                            else:
                                Model.objects.create(**record)
                                stdout.write(
                                    style.SUCCESS(
                                        f"Created {model_name} record successfully"
                                    )
                                )
                        except Exception as e:
                            stdout.write(
                                style.ERROR(
                                    f"Error creating {model_name} record: {str(e)}"
                                )
                            )
                            raise

            stdout.write(
                style.SUCCESS(
                    f"Successfully imported data for tenant {schema_name}"
                )
            )

    except Exception as e:
        stderr.write(style.ERROR(f"Error importing data: {str(e)}"))
        raise
