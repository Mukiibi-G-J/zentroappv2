from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, schema_context
from expenses.models import ExpenseType, ExpenseCategory
from financials.models import G_LAccount


class Command(BaseCommand):
    help = "Create default expense types for all tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing expense types before seeding",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            metavar="SCHEMA",
            help="Only this schema_name. If omitted, all tenant companies (excl. public).",
        )

    def handle(self, *args, **options):
        clear_existing = options.get("clear", False)
        specific_tenant = options.get("tenant")

        self.stdout.write("Creating default expense types...")

        # Define default expense types (each ties back to a seeded category)
        expense_types_data = [
            {
                "code": "OFFICE",
                "name": "Office Supplies",
                "description": "Office supplies and stationery expenses",
                "category_code": "OFFICE",
                "gl_account_no": "8210",
            },
            {
                "code": "UTILITIES",
                "name": "Electricity and Heating",
                "description": "Electricity, water, internet, and other utility expenses",
                "category_code": "UTILITIES",
                "gl_account_no": "8120",
            },
            {
                "code": "PHONE",
                "name": "Phone and Fax",
                "description": "Telephone and fax expenses",
                "category_code": "PHONE",
                "gl_account_no": "8230",
            },
            {
                "code": "POSTAGE",
                "name": "Postage",
                "description": "Postage and courier expenses",
                "category_code": "POSTAGE",
                "gl_account_no": "8240",
            },
            {
                "code": "SALARY",
                "name": "Salaries",
                "description": "Employee salaries and wages",
                "category_code": "SALARY",
                "gl_account_no": "8720",
            },
            {
                "code": "WAGES",
                "name": "Wages",
                "description": "Employee wages and hourly pay",
                "category_code": "WAGES",
                "gl_account_no": "8710",
            },
            {
                "code": "ADVERT",
                "name": "Advertising",
                "description": "Marketing and advertising expenses",
                "category_code": "ADVERT",
                "gl_account_no": "8410",
            },
            {
                "code": "TRAVEL",
                "name": "Travel",
                "description": "Business travel and transportation expenses",
                "category_code": "TRAVEL",
                "gl_account_no": "8430",
            },
            {
                "code": "ENTERTAIN",
                "name": "Entertainment and PR",
                "description": "Meals and entertainment expenses",
                "category_code": "ENTERTAIN",
                "gl_account_no": "8420",
            },
            {
                "code": "MAINTEN",
                "name": "Repairs and Maintenance",
                "description": "Equipment and facility maintenance expenses",
                "category_code": "MAINTEN",
                "gl_account_no": "8130",
            },
            {
                "code": "CLEANING",
                "name": "Cleaning",
                "description": "Cleaning and janitorial services",
                "category_code": "CLEANING",
                "gl_account_no": "8110",
            },
            {
                "code": "SOFTWARE",
                "name": "Software",
                "description": "Software licenses and subscriptions",
                "category_code": "SOFTWARE",
                "gl_account_no": "8310",
            },
            {
                "code": "CONSULT",
                "name": "Consultant Services",
                "description": "Professional consulting services",
                "category_code": "CONSULT",
                "gl_account_no": "8320",
            },
            {
                "code": "DELIVERY",
                "name": "Delivery Expenses",
                "description": "Delivery and shipping expenses",
                "category_code": "DELIVERY",
                "gl_account_no": "8450",
            },
            {
                "code": "BAD_DEBT",
                "name": "Bad Debt Expenses",
                "description": "Bad debt and write-off expenses",
                "category_code": "BAD_DEBT",
                "gl_account_no": "8620",
            },
            {
                "code": "CASH_DISC",
                "name": "Cash Discrepancies",
                "description": "Cash discrepancies and losses",
                "category_code": "CASH_DISC",
                "gl_account_no": "8610",
            },
            {
                "code": "MISC",
                "name": "Miscellaneous",
                "description": "Other miscellaneous expenses",
                "category_code": "MISC",
                "gl_account_no": "8640",
            },
            {
                "code": "RENT",
                "name": "Rent Expenses",
                "description": "Office and facility rental expenses",
                "category_code": "RENT",
                "gl_account_no": "8150",
            },
            {
                "code": "INSURANCE",
                "name": "Insurance",
                "description": "Business insurance and premium expenses",
                "category_code": "MISC",
                "gl_account_no": "8640",
            },
            {
                "code": "TRAINING",
                "name": "Training and Development",
                "description": "Employee training and professional development expenses",
                "category_code": "MISC",
                "gl_account_no": "8640",
            },
        ]

        from company.models import Company

        if specific_tenant:
            try:
                tenants = [Company.objects.get(schema_name=specific_tenant)]
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Tenant '{specific_tenant}' not found!")
                )
                return
        else:
            public = get_public_schema_name()
            tenants = list(Company.objects.exclude(schema_name=public))
            if not tenants:
                self.stdout.write(
                    self.style.WARNING("No tenant companies found to seed.")
                )
                return

        total_created = 0
        total_updated = 0
        total_skipped = 0

        for tenant in tenants:
            self.stdout.write(f"\nProcessing tenant: {tenant.schema_name}")

            with schema_context(tenant.schema_name):
                created_count = 0
                updated_count = 0
                skipped_count = 0

                # Clear existing expense types if requested
                if clear_existing:
                    deleted_count = ExpenseType.objects.all().delete()[0]
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Cleared {deleted_count} existing expense types"
                        )
                    )

                for data in expense_types_data:
                    category = ExpenseCategory.objects.filter(
                        code=data["category_code"]
                    ).first()
                    if not category:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Skipping {data['name']} (category {data['category_code']} missing)"
                            )
                        )
                        continue

                    # Ensure category has a default G/L account (fallback to historic mapping if needed)
                    if not category.default_gl_account:
                        gl_account = G_LAccount.objects.filter(
                            no=data.get("gl_account_no")
                        ).first()
                        if gl_account:
                            category.default_gl_account = gl_account
                            category.save(update_fields=["default_gl_account"])

                    defaults = {
                        "name": data["name"],
                        "description": data["description"],
                        "category": category,
                        "gl_account": category.default_gl_account,
                        "is_active": True,
                        "is_user_defined": False,
                    }

                    expense_type, created = ExpenseType.objects.get_or_create(
                        code=data["code"], defaults=defaults
                    )

                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Created: {expense_type.code} - {expense_type.name}"
                            )
                        )
                        created_count += 1
                    else:
                        # Update existing expense type
                        updated_fields = []
                        if expense_type.name != data["name"]:
                            expense_type.name = data["name"]
                            updated_fields.append("name")
                        if expense_type.description != data["description"]:
                            expense_type.description = data["description"]
                            updated_fields.append("description")
                        if expense_type.category != category:
                            expense_type.category = category
                            updated_fields.append("category")
                        effective_gl = category.default_gl_account
                        if expense_type.gl_account != effective_gl:
                            expense_type.gl_account = effective_gl
                            updated_fields.append("gl_account")
                        if not expense_type.is_active:
                            expense_type.is_active = True
                            updated_fields.append("is_active")
                        if expense_type.is_user_defined:
                            expense_type.is_user_defined = False
                            updated_fields.append("is_user_defined")

                        if updated_fields:
                            expense_type.save(update_fields=updated_fields)
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Updated: {expense_type.code} - {expense_type.name}"
                                )
                            )
                            updated_count += 1
                        else:
                            self.stdout.write(
                                f"  Exists: {expense_type.code} - {expense_type.name}"
                            )
                            skipped_count += 1

                total_created += created_count
                total_updated += updated_count
                total_skipped += skipped_count

                self.stdout.write(
                    f"  Summary for {tenant.schema_name}:"
                    f" Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}"
                )

        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Total across all tenants:"
                f"\n- Created: {total_created} expense types"
                f"\n- Updated: {total_updated} expense types"
                f"\n- Skipped: {total_skipped} expense types"
            )
        )

        # Show usage examples
        self.stdout.write(
            self.style.SUCCESS(
                "\nUsage:"
                "\n  python manage.py seed_expense_types"
                "\n  python manage.py seed_expense_types --tenant=YOUR_SCHEMA"
                "\n  python manage.py seed_expense_types --clear [--tenant=YOUR_SCHEMA]"
            )
        )
