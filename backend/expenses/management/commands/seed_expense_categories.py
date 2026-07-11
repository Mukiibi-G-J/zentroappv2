from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, schema_context

from expenses.models import ExpenseCategory
from financials.models import G_LAccount


class Command(BaseCommand):
    help = (
        "Create default expense categories per tenant schema. "
        "Without --tenant, seeds every Company except the public schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            metavar="SCHEMA",
            help="Only this tenant schema_name (e.g. hardwareworld). "
            "If omitted, all tenant companies are seeded.",
        )

    def handle(self, *args, **options):
        specific_tenant = options.get("tenant")

        self.stdout.write("Creating default expense categories...")

        category_data = [
            {
                "code": "OFFICE",
                "name": "Office Supplies",
                "description": "Office supplies and stationery expenses",
                "icon": "OfficeSupplies",
                "gl_account_no": "8210",
            },
            {
                "code": "RENT",
                "name": "Rent",
                "description": "Office and facility rental expenses",
                "icon": "Building",
                "gl_account_no": "8150",
            },
            {
                "code": "UTILITIES",
                "name": "Utilities",
                "description": "Electricity, water, internet, and other utility expenses",
                "icon": "Utilities",
                "gl_account_no": "8120",
            },
            {
                "code": "PHONE",
                "name": "Phone and Fax",
                "description": "Telephone and fax expenses",
                "icon": "Phone",
                "gl_account_no": "8230",
            },
            {
                "code": "POSTAGE",
                "name": "Postage",
                "description": "Postage and courier expenses",
                "icon": "Mail",
                "gl_account_no": "8240",
            },
            {
                "code": "SALARY",
                "name": "Salaries",
                "description": "Employee salaries and wages",
                "icon": "Users",
                "gl_account_no": "8720",
            },
            {
                "code": "WAGES",
                "name": "Wages",
                "description": "Employee wages and hourly pay",
                "icon": "Users",
                "gl_account_no": "8710",
            },
            {
                "code": "ADVERT",
                "name": "Advertising",
                "description": "Marketing and advertising expenses",
                "icon": "Megaphone",
                "gl_account_no": "8410",
            },
            {
                "code": "TRAVEL",
                "name": "Travel",
                "description": "Business travel and transportation expenses",
                "icon": "Globe",
                "gl_account_no": "8430",
            },
            {
                "code": "ENTERTAIN",
                "name": "Entertainment & PR",
                "description": "Meals, entertainment, and PR expenses",
                "icon": "Gift",
                "gl_account_no": "8420",
            },
            {
                "code": "MAINTEN",
                "name": "Repairs & Maintenance",
                "description": "Equipment and facility maintenance expenses",
                "icon": "Toolbox",
                "gl_account_no": "8130",
            },
            {
                "code": "CLEANING",
                "name": "Cleaning",
                "description": "Cleaning and janitorial services",
                "icon": "Broom",
                "gl_account_no": "8110",
            },
            {
                "code": "SOFTWARE",
                "name": "Software",
                "description": "Software licenses and subscriptions",
                "icon": "Chip",
                "gl_account_no": "8310",
            },
            {
                "code": "CONSULT",
                "name": "Consultant Services",
                "description": "Professional consulting services",
                "icon": "Briefcase",
                "gl_account_no": "8320",
            },
            {
                "code": "DELIVERY",
                "name": "Delivery Expenses",
                "description": "Delivery and shipping expenses",
                "icon": "Truck",
                "gl_account_no": "8450",
            },
            {
                "code": "BAD_DEBT",
                "name": "Bad Debt Expenses",
                "description": "Bad debt and write-off expenses",
                "icon": "AlertCircle",
                "gl_account_no": "8620",
            },
            {
                "code": "CASH_DISC",
                "name": "Cash Discrepancies",
                "description": "Cash discrepancies and losses",
                "icon": "AlertTriangle",
                "gl_account_no": "8610",
            },
            {
                "code": "MISC",
                "name": "Miscellaneous",
                "description": "Other miscellaneous expenses",
                "icon": "DotsHorizontal",
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

        for tenant in tenants:
            self.stdout.write(f"\nProcessing tenant: {tenant.schema_name}")

            with schema_context(tenant.schema_name):
                created_count = 0
                updated_count = 0

                for data in category_data:
                    gl_account = None
                    gl_account_no = data.get("gl_account_no")
                    if gl_account_no:
                        gl_account = G_LAccount.objects.filter(
                            no=gl_account_no
                        ).first()
                        if not gl_account:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  G/L account {gl_account_no} not found for "
                                    f"{data['code']}; default_gl_account left unset"
                                )
                            )

                    category, created = ExpenseCategory.objects.get_or_create(
                        code=data["code"],
                        defaults={
                            "name": data["name"],
                            "description": data["description"],
                            "icon": data.get("icon"),
                            "default_gl_account": gl_account,
                            "is_active": True,
                            "is_system": True,
                        },
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Created category: {category.code} - {category.name}"
                            )
                        )
                        continue

                    updated = False
                    if category.name != data["name"]:
                        category.name = data["name"]
                        updated = True
                    if category.description != data["description"]:
                        category.description = data["description"]
                        updated = True
                    if category.icon != data.get("icon"):
                        category.icon = data.get("icon")
                        updated = True
                    if gl_account and category.default_gl_account != gl_account:
                        category.default_gl_account = gl_account
                        updated = True
                    if not category.is_active:
                        category.is_active = True
                        updated = True
                    if not category.is_system:
                        category.is_system = True
                        updated = True

                    if updated:
                        category.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Updated category: {category.code} - {category.name}"
                            )
                        )

                total_created += created_count
                total_updated += updated_count

                self.stdout.write(
                    f"  Summary for {tenant.schema_name}: Created {created_count}, Updated {updated_count}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Total across all tenants:"
                f"\n- Created: {total_created} categories"
                f"\n- Updated: {total_updated} categories"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\nUsage:"
                "\n  python manage.py seed_expense_categories"
                "\n  python manage.py seed_expense_categories --tenant=YOUR_SCHEMA"
                "\nThen (optional) link types: python manage.py seed_expense_types [--tenant=YOUR_SCHEMA]"
            )
        )
