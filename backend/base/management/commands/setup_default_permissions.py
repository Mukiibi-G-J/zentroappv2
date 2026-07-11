from django.core.management.base import BaseCommand
from base.models import PermissionSet, PermissionSetLine, Objects
from authentication.models import Role


class Command(BaseCommand):
    help = "Create default permission sets for common roles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing permission sets instead of skipping them",
        )

    def handle(self, *args, **options):
        update_existing = options.get("update", False)

        self.stdout.write(
            self.style.SUCCESS("\n🔐 Setting up default permission sets...\n")
        )

        # Get or create roles (using your existing roles)
        admin_role, _ = Role.objects.get_or_create(
            name="Admin", defaults={"description": "Administrator with full access"}
        )
        manager_role, _ = Role.objects.get_or_create(
            name="Manager", defaults={"description": "Manager with broad access"}
        )
        cashier_role, _ = Role.objects.get_or_create(
            name="Cashier", defaults={"description": "Cashier for POS operations"}
        )
        sales_role, _ = Role.objects.get_or_create(
            name="Sales", defaults={"description": "Sales team member"}
        )
        inventory_role, _ = Role.objects.get_or_create(
            name="Inventory", defaults={"description": "Inventory management"}
        )

        # 1. ADMIN Permission Set - Full Access
        admin_perm, created = PermissionSet.objects.get_or_create(
            code="ADMIN_FULL",
            defaults={
                "name": "Admin - Full Access",
                "description": "Full access to all objects and actions",
                "is_system": True,
                "linked_role": admin_role,
            },
        )

        if created or update_existing:
            # Give admin full access to all objects
            admin_perm.permission_lines.all().delete()  # Clear existing if updating

            for obj in Objects.objects.filter(requires_permission=True):
                PermissionSetLine.objects.create(
                    permission_set=admin_perm,
                    application_object=obj,
                    read_permission="yes",
                    insert_permission="yes",
                    modify_permission="yes",
                    delete_permission="yes",
                    execute_permission="yes",
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {'Updated' if update_existing else 'Created'} ADMIN_FULL permission set ({admin_perm.permission_lines.count()} objects)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  ADMIN_FULL already exists (use --update to refresh)"
                )
            )

        # 2. MANAGER Permission Set - Most Access, Limited Deletions
        manager_perm, created = PermissionSet.objects.get_or_create(
            code="MANAGER",
            defaults={
                "name": "Manager",
                "description": "Manager with most access, some delete restrictions",
                "is_system": True,
                "linked_role": manager_role,
            },
        )

        if created or update_existing:
            manager_perm.permission_lines.all().delete()

            # Define manager permissions
            manager_object_ids = {
                2100: {"delete": "yes"},  # CustomUser
                2101: {"delete": "yes"},  # Role
                2200: {"delete": "none"},  # Company - cannot delete
                2204: {"delete": "yes"},  # PaymentMethod
                2500: {"delete": "yes"},  # Item
                2501: {"delete": "yes"},  # ItemCategory
                2502: {"delete": "yes"},  # UnitOfMeasure
                2600: {"delete": "yes"},  # Customer
                2601: {"delete": "yes"},  # CustomerGroup
                2701: {"delete": "yes"},  # Sale
                2702: {"delete": "yes"},  # SaleLine
                2900: {"delete": "none"},  # Posting - cannot delete
                2901: {"delete": "none"},  # PostingLine - cannot delete
                3101: {"delete": "yes"},  # PurchaseInvoice
                3102: {"delete": "yes"},  # PurchaseInvoiceLine
            }

            for obj_id, perms in manager_object_ids.items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)
                    PermissionSetLine.objects.create(
                        permission_set=manager_perm,
                        application_object=obj,
                        read_permission="yes",
                        insert_permission="yes",
                        modify_permission="yes",
                        delete_permission=perms.get("delete", "yes"),
                        execute_permission="yes",
                    )
                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Object {obj_id} not found, skipping")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {'Updated' if update_existing else 'Created'} MANAGER permission set ({manager_perm.permission_lines.count()} objects)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  MANAGER already exists (use --update to refresh)"
                )
            )

        # 3. CASHIER Permission Set - POS Focus
        cashier_perm, created = PermissionSet.objects.get_or_create(
            code="CASHIER",
            defaults={
                "name": "Cashier",
                "description": "POS operations and basic customer access",
                "is_system": True,
                "linked_role": cashier_role,
            },
        )

        if created or update_existing:
            cashier_perm.permission_lines.all().delete()

            # Define cashier permissions
            cashier_objects = {
                2600: {
                    "read": "yes",
                    "insert": "yes",
                    "modify": "yes",
                    "delete": "none",
                },  # Customer
                2500: {
                    "read": "yes",
                    "insert": "none",
                    "modify": "none",
                    "delete": "none",
                },  # Item - read only
                2701: {
                    "read": "yes",
                    "insert": "yes",
                    "modify": "yes",
                    "delete": "none",
                },  # Sale
                2702: {
                    "read": "yes",
                    "insert": "yes",
                    "modify": "yes",
                    "delete": "none",
                },  # SaleLine
                2204: {
                    "read": "yes",
                    "insert": "none",
                    "modify": "none",
                    "delete": "none",
                },  # PaymentMethod - read only
            }

            for obj_id, perms in cashier_objects.items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)
                    PermissionSetLine.objects.create(
                        permission_set=cashier_perm,
                        application_object=obj,
                        read_permission=perms.get("read", "none"),
                        insert_permission=perms.get("insert", "none"),
                        modify_permission=perms.get("modify", "none"),
                        delete_permission=perms.get("delete", "none"),
                        execute_permission="none",
                    )
                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Object {obj_id} not found, skipping")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {'Updated' if update_existing else 'Created'} CASHIER permission set ({cashier_perm.permission_lines.count()} objects)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  CASHIER already exists (use --update to refresh)"
                )
            )

        # 4. SALES Permission Set - Sales Focus
        sales_perm, created = PermissionSet.objects.get_or_create(
            code="SALES",
            defaults={
                "name": "Sales",
                "description": "Sales team with customer and sales access",
                "is_system": True,
                "linked_role": sales_role,
            },
        )

        if created or update_existing:
            sales_perm.permission_lines.all().delete()

            # Define sales permissions
            sales_objects = {
                2600: {"delete": "none"},  # Customer - no delete
                2601: {"delete": "none"},  # CustomerGroup - no delete
                2500: {
                    "read": "yes",
                    "insert": "none",
                    "modify": "none",
                    "delete": "none",
                },  # Item - read only
                2701: {"delete": "none"},  # Sale - no delete
                2702: {"delete": "none"},  # SaleLine - no delete
            }

            for obj_id, perms in sales_objects.items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)
                    PermissionSetLine.objects.create(
                        permission_set=sales_perm,
                        application_object=obj,
                        read_permission=perms.get("read", "yes"),
                        insert_permission=perms.get("insert", "yes"),
                        modify_permission=perms.get("modify", "yes"),
                        delete_permission=perms.get("delete", "yes"),
                        execute_permission="none",
                    )
                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Object {obj_id} not found, skipping")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {'Updated' if update_existing else 'Created'} SALES permission set ({sales_perm.permission_lines.count()} objects)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"  SALES already exists (use --update to refresh)")
            )

        # 5. INVENTORY Permission Set - Inventory Focus
        inventory_perm, created = PermissionSet.objects.get_or_create(
            code="INVENTORY",
            defaults={
                "name": "Inventory",
                "description": "Inventory management and stock control",
                "is_system": True,
                "linked_role": inventory_role,
            },
        )

        if created or update_existing:
            inventory_perm.permission_lines.all().delete()

            # Define inventory permissions
            inventory_objects = {
                2500: {"delete": "yes"},  # Item
                2501: {"delete": "yes"},  # ItemCategory
                2502: {"delete": "yes"},  # UnitOfMeasure
                2503: {"delete": "none"},  # ItemJournal - no delete
                2505: {
                    "read": "yes",
                    "insert": "none",
                    "modify": "none",
                    "delete": "none",
                },  # ItemLedgerEntries - read only
                2600: {
                    "read": "yes",
                    "insert": "none",
                    "modify": "none",
                    "delete": "none",
                },  # Customer - read only
            }

            for obj_id, perms in inventory_objects.items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)
                    PermissionSetLine.objects.create(
                        permission_set=inventory_perm,
                        application_object=obj,
                        read_permission=perms.get("read", "yes"),
                        insert_permission=perms.get("insert", "yes"),
                        modify_permission=perms.get("modify", "yes"),
                        delete_permission=perms.get("delete", "yes"),
                        execute_permission="none",
                    )
                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Object {obj_id} not found, skipping")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {'Updated' if update_existing else 'Created'} INVENTORY permission set ({inventory_perm.permission_lines.count()} objects)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  INVENTORY already exists (use --update to refresh)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\n✅ Default permission sets setup complete!\n\nYou can now:"
            )
        )
        self.stdout.write("  • View permission sets in Django Admin")
        self.stdout.write("  • Assign users to roles (existing system)")
        self.stdout.write("  • Permission sets automatically apply through role links")
        self.stdout.write(
            "\n💡 Tip: Run 'python manage.py setup_default_permissions --update' to refresh all sets\n"
        )



