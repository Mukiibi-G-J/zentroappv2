from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction, connection
from base.models import Objects, ObjectType
from django_tenants.utils import tenant_context
from company.models import Company  # Import your actual tenant model
from core.settings import TENANT_APPS, SHARED_APPS

# Mapping of tables to their consistent object IDs
TABLE_OBJECT_IDS = {
    # System tables (1000-1099)
    "admin_logentry": 1000,
    "auth_permission": 1001,
    "auth_group": 1002,
    "auth_user": 1003,
    "contenttypes_contenttype": 1004,
    "sessions_session": 1005,
    "django_celery_beat_clockedschedule": 1006,
    "django_celery_beat_crontabschedule": 1007,
    "django_celery_beat_intervalschedule": 1008,
    "django_celery_beat_periodictask": 1009,
    "django_celery_beat_solarschedule": 1010,
    "django_celery_results_chordcounter": 1011,
    "django_celery_results_groupresult": 1012,
    "django_celery_results_taskresult": 1013,
    # Base & Common (2000-2099)
    "base_objects": 2000,
    # Authentication (2100-2199)
    "authentication_customuser": 2100,
    "authentication_role": 2101,  # MISSING
    "authentication_profile": 2102,  # MISSING
    "authentication_otp": 2103,
    # Company (2200-2299)
    "company_company": 2200,
    "company_domain": 2201,
    "company_paymentgateway": 2202,  # MISSING
    "company_subscription": 2203,  # MISSING
    "company_paymentmethod": 2204,
    "company_billinghistory": 2205,  # MISSING
    "company_businesscategory": 2206,  # MISSING
    "company_businessobjective": 2207,  # MISSING
    "company_companyonboarding": 2208,  # MISSING
    "company_pricing": 2209,  # MISSING
    # Setup (2300-2399)
    "setup_emailsetup": 2300,
    "setup_sitesettings": 2301,
    "setup_noseries": 2302,  # MISSING
    "setup_noserieslines": 2303,
    "setup_inventorysetup": 2304,
    "setup_journalsetup": 2305,
    "setup_uploadtemplates": 2306,
    "setup_paymentmethod": 2307,  # MISSING
    # Config Packages (2400-2499)
    "config_packages_configpackage": 2400,
    "config_packages_configpackagetable": 2401,
    "config_packages_uploadtemplates": 2402,
    # Items (2500-2599)
    "items_item": 2500,
    "items_itemcategory": 2501,
    "items_unitofmeasure": 2502,
    "items_itemjournal": 2503,
    "items_itemimages": 2504,
    "items_itemledgerentries": 2505,
    "items_valueentry": 2506,
    "items_itemunitofmeasure": 2507,  # MISSING
    "items_itemtrackingcodes": 2508,  # MISSING
    "items_trackingspecification": 2509,  # MISSING
    "items_location": 2510,  # MISSING
    # Customers (2600-2699)
    "customers_customer": 2600,
    "customers_customergroup": 2601,
    "customers_customerpostinggroup": 2602,
    "customers_customerledgerentry": 2603,
    # Sales (2700-2799)
    "sales_salesreceivable": 2700,  # MISSING
    "sales_sale": 2701,
    "sales_customer": 2708,  # For DefaultDimension lookup
    "sales_saleline": 2702,
    "sales_postedsalesinvoice": 2703,  # MISSING
    "sales_postedsalesinvoiceline": 2704,  # MISSING
    "sales_customerpostinggroup": 2705,  # MISSING
    "sales_customerledgerentry": 2706,  # MISSING
    "sales_detailedcustomerledgerentry": 2707,  # MISSING
    # Financials (2800-2899)
    "financials_g_laccount": 2800,  # MISSING
    "financials_generalledgerentry": 2801,  # MISSING
    "financials_generalledgersetup": 2802,  # MISSING
    "financials_paymentmethod": 2803,  # MISSING
    "financials_paymentbatch": 2804,  # MISSING
    "financials_payment": 2805,  # MISSING
    "financials_financialreport": 2806,
    "financials_financialreportrowgroup": 2807,
    "financials_financialreportcolumngroup": 2808,
    "financials_financialreportrowline": 2809,
    "financials_financialreportcolumnline": 2810,
    # Postings (2900-2999)
    "postings_posting": 2900,
    "postings_postingline": 2901,
    "postings_generalproductpostinggroup": 2902,
    "postings_generalbusinesspostinggroup": 2903,
    "postings_generalpostingsetup": 2904,
    "postings_inventorypostinggroup": 2905,
    "postings_inventorypostingsetup": 2906,
    "postings_dimensionvalue": 2907,
    "postings_dimension": 2908,
    "postings_vatproductpostinggroup": 2909,  # MISSING
    "postings_vatbusinesspostinggroup": 2910,  # MISSING
    # Purchases (3100-3199)
    "purchases_purchasepayable": 3100,  # MISSING
    "purchases_purchaseinvoice": 3101,
    "purchases_purchaseinvoiceline": 3102,
    "purchases_postedpurchaseinvoice": 3103,  # MISSING
    "purchases_postedpurchaseinvoiceline": 3104,  # MISSING
    "purchases_vendorledger": 3105,  # MISSING
    "purchases_vendorpostinggroup": 3106,
    "purchases_vendor": 3107,
    "purchases_detailedvendorledgerentry": 3108,  # MISSING
    # Payments (3200-3299) - NEW CATEGORY
    "payments_paymentjournal": 3200,  # MISSING
    # Dimension (3300-3399) - NEW CATEGORY
    "dimension_dimension": 3300,  # MISSING
    "dimension_dimensionvalue": 3301,  # MISSING
    # Restaurant (3400-3499)
    "restaurant_management_restaurantorder": 3400,
    "restaurant_management_restaurantorderitem": 3401,
    "restaurant_management_table": 3402,
    "restaurant_management_reservation": 3403,
    "restaurant_management_menuitem": 3404,
    "restaurant_management_menucategory": 3405,
    "restaurant_management_menu": 3406,
    "restaurant_management_floor": 3407,
    # Sales documents (3500-3599) — BC table-data enforcement
    "sales_salesorder": 3500,
    "sales_salesorderline": 3501,
    "sales_salesinvoice": 3502,
    "sales_salesinvoiceline": 3503,
    # Expenses / bank (3600-3699)
    "expenses_expense": 3600,
    "bank_account_bankaccount": 3601,
    "payments_paymentline": 3602,
}


class Command(BaseCommand):
    help = "Populates the Objects table with all tables in the application"

    def table_exists(self, table_name, schema_name="public"):
        """Check if a table exists in the specified schema"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_name = %s
                );
            """,
                [schema_name, table_name],
            )
            return cursor.fetchone()[0]

    def handle(self, *args, **options):
        try:
            # First check if base_objects table exists in public schema
            if not self.table_exists("base_objects"):
                self.stdout.write(
                    self.style.WARNING(
                        "Objects table does not exist. Please run migrations first."
                    )
                )
                return

            # Get or create the TABLE object type
            table_obj_type, _ = ObjectType.objects.get_or_create(
                code="TABLE",
                defaults={
                    "name": "Table",
                    "description": "Database tables and models",
                    "sort_order": 1,
                },
            )

            # Get the first tenant to check tenant-specific tables
            tenant = Company.objects.first()
            if not tenant:
                self.stdout.write(
                    self.style.WARNING("No tenant found. Please create a tenant first.")
                )
                return

            try:
                # Try to safely delete all entries
                Objects.objects.all().delete()
            except Exception as e:
                # If deletion fails, try to delete entries one by one
                self.stdout.write(
                    self.style.WARNING("Falling back to individual deletion")
                )
                for obj in Objects.objects.all():
                    try:
                        obj.delete()
                    except Exception:
                        continue

            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully cleared existing entries from Objects table"
                )
            )

            # Define app categories
            django_apps = [
                "django",
                "admin",
                "auth",
                "contenttypes",
                "sessions",
                "messages",
                "staticfiles",
            ]

            third_party_apps = [
                "django_celery_beat",
                "django_celery_results",
                "admin_searchable_dropdown",
                "widget_tweaks",
                "django_htmx",
                "django_select2",
                "mptt",
                "rest_framework",
                "corsheaders",
                "django_filters",
                "rest_framework_simplejwt",
            ]

            # Get all models from both shared and tenant apps
            for model in apps.get_models():
                try:
                    app_label = model._meta.app_label
                    model_name = model._meta.model_name
                    table_name = model._meta.db_table

                    # Skip abstract models
                    if model._meta.abstract:
                        continue

                    # Check if table exists in appropriate schema
                    table_exists = False
                    if app_label in [app.split(".")[-1] for app in SHARED_APPS]:
                        # Check public schema for shared apps
                        table_exists = self.table_exists(table_name)
                    else:
                        # Check tenant schema for tenant apps
                        with tenant_context(tenant):
                            table_exists = self.table_exists(
                                table_name, tenant.schema_name
                            )

                    if not table_exists:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {table_name}: table does not exist in appropriate schema"
                            )
                        )
                        continue

                    # Determine table type
                    if any(app_label.startswith(sys_app) for sys_app in django_apps):
                        subtype = "System"
                    elif app_label in third_party_apps:
                        subtype = "ThirdParty"
                    else:
                        subtype = "Custom"

                    # Get verbose name and format table name
                    verbose_name = model._meta.verbose_name.title()
                    model_class_name = model.__name__

                    # Get object ID
                    table_key = f"{app_label}_{model_name}"
                    object_id = TABLE_OBJECT_IDS.get(table_key, 5000)

                    # Create or update Objects entry (keyed by object_id for stable BC IDs)
                    obj, created = Objects.objects.update_or_create(
                        object_id=object_id,
                        defaults={
                            "object_name": model_class_name,
                            "object_type": "Table",
                            "object_type_ref": table_obj_type,
                            "app_label": app_label,
                            "object_caption": verbose_name,
                            "object_subtype": subtype,
                            "requires_permission": True,
                            "related_model": f"{app_label}.{model_class_name}",
                            "is_active": True,
                        },
                    )

                    if created:
                        schema = (
                            "public"
                            if app_label in [app.split(".")[-1] for app in SHARED_APPS]
                            else tenant.schema_name
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Added table: {model_class_name} ({subtype}) from {app_label} in {schema} schema"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Error processing {app_label}.{model_name}: {str(e)}"
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to populate Objects table: {str(e)}")
            )
