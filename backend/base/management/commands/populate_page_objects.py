"""
Management command to populate Page objects for the permission system
This creates Page objects that map to actual frontend routes/components

Usage:
    python manage.py tenant_command populate_page_objects --schema=hardwareworld
"""

from django.core.management.base import BaseCommand
from base.models import Objects, ObjectType


class Command(BaseCommand):
    help = "Populate Page objects for permission system"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("POPULATING PAGE OBJECTS"))
        self.stdout.write("=" * 80 + "\n")

        # Get or create Page object type (lookup by unique code, not name)
        page_type, created = ObjectType.objects.get_or_create(
            code="PAGE",
            defaults={
                "name": "Page",
                "description": "Application pages and routes that users can access",
                "sort_order": 2,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS("✅ Created Page object type"))
        else:
            self.stdout.write(self.style.WARNING("Page object type already exists"))

        # Define all page objects based on actual routes
        # Format: (object_id, name, module_code, description, route)
        pages_to_create = [
            # ============================================
            # SALES MODULE PAGES
            # ============================================
            (
                10001,
                "Sales Dashboard",
                "sales",
                "Sales analytics dashboard with metrics and charts",
                "/app/sales/dashboard",
            ),
            (
                10002,
                "Sales",
                "sales",
                "POS/Sales entry page for creating new sales",
                "/app/sales",
            ),
            (
                10003,
                "Sales Invoice Page",
                "sales",
                "Sales invoice management page",
                "/app/sales/sales-invoice",
            ),
            (
                10004,
                "Sales History",
                "sales",
                "Posted sales history and reports",
                "/app/sales/sales-history",
            ),
            (
                10005,
                "Sales Order Page",
                "sales",
                "Sales order entry and management page (no posting)",
                "/app/sales/sales-order",
            ),
            # ============================================
            # PREPAYMENTS MODULE PAGES
            # ============================================
            (
                11001,
                "Prepayments",
                "prepayments",
                "Customer prepayment dashboard, detail, and posting workspace",
                "/app/prepayments",
            ),
            # ============================================
            # CUSTOMERS MODULE PAGES
            # ============================================
            (
                10101,
                "Customer Management",
                "customers",
                "Manage all customer records (view, create, edit, delete)",
                "/app/customers",
            ),
            # ============================================
            # ITEMS MODULE PAGES
            # ============================================
            (
                10201,
                "Items",
                "items",
                "Item/product management (view, create, edit, delete)",
                "/app/items",
            ),
            (
                10202,
                "Adjust Inventory",
                "items",
                "Inventory adjustment entry page",
                "/app/items/adjust-inventory",
            ),
            (
                10203,
                "Adjust Inventory History",
                "items",
                "Inventory adjustment history and reports",
                "/app/items/adjust-inventory-history",
            ),
            (
                10204,
                "Item Categories",
                "items",
                "Item category management (view, create, edit, delete)",
                "/app/items/categories",
            ),
            (
                10205,
                "Stock Taking",
                "items",
                "Physical inventory counting and stock taking",
                "/app/items/stock-taking",
            ),
            # ============================================
            # PURCHASES MODULE PAGES
            # ============================================
            (
                10301,
                "Purchases",
                "purchases",
                "Purchase order management (view, create, edit, delete)",
                "/app/purchases",
            ),
            (
                10302,
                "Purchase History",
                "purchases",
                "Posted purchase order history and reports",
                "/app/purchases/purchases-history",
            ),
            # ============================================
            # SUPPLIERS MODULE PAGES
            # ============================================
            (
                10303,
                "Suppliers",
                "suppliers",
                "Supplier/vendor management (view, create, edit, delete)",
                "/app/suppliers",
            ),
            # ============================================
            # PAYMENTS MODULE PAGES
            # ============================================
            (
                10401,
                "Payments",
                "payments",
                "Payment processing and management",
                "/app/payments",
            ),
            (
                10402,
                "Payment History",
                "payments",
                "Posted payment history and transaction records",
                "/app/payments/payment-history",
            ),
            (
                10403,
                "Payment Methods",
                "payments",
                "Payment method configuration and management",
                "/app/payments/payment-methods",
            ),
            # ============================================
            # FINANCIALS MODULE PAGES
            # ============================================
            (
                10501,
                "Chart of Accounts",
                "financials",
                "Chart of accounts management",
                "/app/financials/chart-of-accounts",
            ),
            (
                10502,
                "Financial Reports",
                "financials",
                "Financial reports and analytics",
                "/app/financials/reports",
            ),
            (
                10503,
                "Profit & Loss",
                "financials",
                "Profit and loss statement",
                "/app/financials/profit-loss-statement",
            ),
            # ============================================
            # REPORTS MODULE PAGES
            # ============================================
            (
                10504,
                "Dimensions",
                "financials",
                "Dimension codes (e.g. BRANCH, DEPARTMENT)",
                "/app/financials/dimensions",
            ),
            (
                10505,
                "Dimension Values",
                "financials",
                "Values for each dimension code",
                "/app/financials/dimension-values",
            ),
            (
                10506,
                "Expiry Report",
                "reports",
                "Inventory expiry report generator (PDF)",
                "/app/reports/expiry",
            ),
            (
                10507,
                "Inventory Transaction Detail Report",
                "reports",
                "Per-item inventory transaction ledger with running balance",
                "/app/reports/inventory-transaction-detail",
            ),
            # ============================================
            # EXPENSES MODULE PAGES
            # ============================================
            (
                10601,
                "Expenses",
                "expenses",
                "Expense tracking and management",
                "/app/expenses",
            ),
            (
                10602,
                "Expense Setup",
                "expenses",
                "Configure expense categories and types",
                "/app/expenses/setup",
            ),
            # ============================================
            # COMPANY/SETTINGS PAGES
            # ============================================
            (
                10701,
                "Company Management",
                "company",
                "Company settings and configuration",
                "/app/company",
            ),
            (
                10702,
                "Role Management",
                "roles",
                "User role and permission management",
                "/app/roles",
            ),
            (
                10703,
                "Profile Settings",
                "profile",
                "User profile and preferences",
                "/app/settings/profile",
            ),
            (
                10704,
                "Receipt Templates",
                "company",
                "Thermal receipt layout and printer assignments",
                "/app/company",
            ),
            # ============================================
            # RESTAURANT MODULE PAGES (IDs: 10710-10718, 10722)
            # ============================================
            (
                10710,
                "Restaurant Dashboard",
                "restaurant",
                "Restaurant dashboard and KPIs",
                "/app/restaurant/dashboard",
            ),
            (
                10711,
                "Table Management",
                "restaurant",
                "Manage tables and floor plans",
                "/app/restaurant/floor-plan",
            ),
            (
                10712,
                "Reservations",
                "restaurant",
                "Restaurant reservations",
                "/app/restaurant/reservations",
            ),
            (
                10713,
                "Orders",
                "restaurant",
                "Restaurant orders and checkout",
                "/app/restaurant/orders",
            ),
            (
                10714,
                "Menu Management",
                "restaurant",
                "Menu categories and items (opens in Menus & catalog)",
                "/app/restaurant/menus?tab=catalog",
            ),
            (
                10715,
                "Kitchen Display",
                "restaurant",
                "Kitchen order display",
                "/app/restaurant/kitchen",
            ),
            (
                10716,
                "Restaurant Settings",
                "restaurant",
                "Restaurant configuration",
                "/app/restaurant/settings",
            ),
            (
                10717,
                "Restaurant POS",
                "restaurant",
                "Table-first POS runtime (floor, check, fire)",
                "/app/restaurant/pos",
            ),
            (
                10718,
                "Menu Layout Editor",
                "restaurant",
                "Unified menu builder: service menus, pages, and POS tiles",
                "/app/restaurant/menus",
            ),
            (
                10722,
                "Restaurant Menus",
                "restaurant",
                "Create POS service menus and link them to locations",
                "/app/restaurant/menus",
            ),
            # Page-engine restaurant pages (BC-style; IDs 10723-10733)
            (
                10723,
                "RestaurantOrderList",
                "restaurant",
                "Restaurant orders list",
                "/dashboard",
            ),
            (
                10724,
                "TableList",
                "restaurant",
                "Restaurant tables and floor plan",
                "/dashboard",
            ),
            (
                10725,
                "ReservationList",
                "restaurant",
                "Restaurant reservations",
                "/dashboard",
            ),
            (
                10726,
                "MenuCategoryList",
                "restaurant",
                "Menu categories",
                "/dashboard",
            ),
            (
                10727,
                "MenuItemList",
                "restaurant",
                "Menu catalog items",
                "/dashboard",
            ),
            (
                10728,
                "MenuList",
                "restaurant",
                "POS service menus",
                "/dashboard",
            ),
            (
                10729,
                "KitchenDisplayList",
                "restaurant",
                "Kitchen display / KDS queue",
                "/dashboard",
            ),
            (
                10730,
                "RestaurantPOS",
                "restaurant",
                "Restaurant point of sale",
                "/dashboard",
            ),
            (
                10735,
                "MenuBuilder",
                "restaurant",
                "Restaurant menu builder (catalog and POS tiles)",
                "/dashboard",
            ),
            (
                10736,
                "KitchenDisplay",
                "restaurant",
                "Kitchen display system (KDS)",
                "/dashboard",
            ),
            (
                10731,
                "FloorList",
                "restaurant",
                "Restaurant floors",
                "/dashboard",
            ),
            (
                10732,
                "RestaurantManagerRC",
                "restaurant",
                "Restaurant manager role centre",
                "/dashboard",
            ),
            (
                10733,
                "RestaurantFOHRC",
                "restaurant",
                "Restaurant front-of-house role centre",
                "/dashboard",
            ),
            (
                10734,
                "RestaurantKitchenRC",
                "restaurant",
                "Restaurant kitchen role centre",
                "/dashboard",
            ),
            # ============================================
            # MANUFACTURING MODULE PAGES (IDs: 10719+)
            # ============================================
            (
                10719,
                "Make Production",
                "manufacturing",
                "Create and manage production orders",
                "/app/manufacturing/make-production",
            ),
            (
                10720,
                "Production BOM Management",
                "manufacturing",
                "Production bill of materials setup",
                "/app/manufacturing/production-bom",
            ),
            (
                10721,
                "Finished Productions",
                "manufacturing",
                "Read-only list of completed (finished) production orders",
                "/app/manufacturing/finished-productions",
            ),
            # ============================================
            # USER MANAGEMENT MODULE PAGES (IDs: 10801-10810)
            # ============================================
            (
                10801,
                "User Management",
                "userManagement",
                "Manage tenant users (view, create, edit, delete)",
                "/app/user-management/users",
            ),
            (
                10802,
                "User Group Management",
                "userManagement",
                "Manage user groups and group assignments",
                "/app/user-management/user-groups",
            ),
            (
                10803,
                "Permission Set Management",
                "userManagement",
                "Manage permission sets and page permissions",
                "/app/user-management/permission-sets",
            ),
            (
                10804,
                "User Roles Management",
                "userManagement",
                "Manage user roles and role center assignments",
                "/app/user-management/roles",
            ),
            (
                10805,
                "Role Center Management",
                "userManagement",
                "Manage role centers and module visibility",
                "/app/user-management/role-centers",
            ),
            # ============================================
            # LOANS MODULE PAGES (IDs: 10806-10807)
            # ============================================
            (
                10806,
                "Loan Registration",
                "loans",
                "Loan registration and management",
                "/app/loans",
            ),
            (
                10807,
                "Loan Repayment",
                "loans",
                "Loan repayment entry and management",
                "/app/loans/repayments",
            ),
            (
                10808,
                "Loan History",
                "loans",
                "Posted loan history and reports",
                "/app/loans/history",
            ),
            (
                10809,
                "Loan Repayment History",
                "loans",
                "Posted loan repayment history and transaction records",
                "/app/loans/repayments/history",
            ),
            # ============================================
            # CONFIGURATION PACKAGES MODULE PAGES (IDs: 10901-10910)
            # ============================================
            (
                10901,
                "Configuration Packages",
                "configPackages",
                "Manage configuration packages for environment setup",
                "/setup/configuration/packages",
            ),
            (
                10902,
                "Tracking Codes",
                "trackingCodes",
                "View dimensions (tracking codes) and drill down to dimension values",
                "/setup/tracking-codes",
            ),
            (
                10903,
                "Tracking Code Values",
                "trackingCodes",
                "View tracking code values for a selected dimension",
                "/setup/tracking-codes/:dimensionId",
            ),
            (
                10904,
                "Branch Management",
                "trackingCodes",
                "Add and view branch locations when your plan allows",
                "/setup/branches",
            ),
            # ============================================
            # BANK ACCOUNT MODULE PAGES (IDs: 11001-11010)
            # ============================================
            (
                11001,
                "Bank Account Management",
                "bankAccount",
                "Manage bank accounts (view, create, edit, delete)",
                "/app/bank-accounts",
            ),
            (
                11002,
                "Bank Account Ledger Entries",
                "bankAccount",
                "View bank account ledger entries and transactions",
                "/app/bank-accounts/ledger-entries",
            ),
        ]

        created_count = 0
        updated_count = 0

        for object_id, name, module_code, description, route in pages_to_create:
            # Check if object with this name already exists
            existing_by_name = Objects.objects.filter(object_name=name).first()

            if existing_by_name:
                # If object exists with same name but different ID, update it in place
                if existing_by_name.object_id != object_id:
                    # Update the existing object with new data (keep its original ID)
                    existing_by_name.object_type = "Page"
                    existing_by_name.object_type_ref = page_type
                    existing_by_name.object_caption = f"{description}\nRoute: {route}"
                    existing_by_name.app_label = module_code
                    existing_by_name.object_subtype = "Custom"
                    existing_by_name.is_active = True
                    existing_by_name.requires_permission = True
                    existing_by_name.save()
                    obj = existing_by_name
                    created = False
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ℹ️  Updated: [{existing_by_name.object_id}] {name} → {route} (kept original ID)"
                        )
                    )
                else:
                    # Same ID, update normally
                    obj, created = Objects.objects.update_or_create(
                        object_id=object_id,
                        defaults={
                            "object_type": "Page",
                            "object_type_ref": page_type,
                            "object_name": name,
                            "object_caption": f"{description}\nRoute: {route}",
                            "app_label": module_code,
                            "object_subtype": "Custom",
                            "is_active": True,
                            "requires_permission": True,
                        },
                    )
            else:
                # No existing object with this name, create/update normally
                obj, created = Objects.objects.update_or_create(
                    object_id=object_id,
                    defaults={
                        "object_type": "Page",
                        "object_type_ref": page_type,
                        "object_name": name,
                        "object_caption": f"{description}\nRoute: {route}",
                        "app_label": module_code,
                        "object_subtype": "Custom",
                        "is_active": True,
                        "requires_permission": True,
                    },
                )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ Created: [{object_id}] {name} → {route}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"  ℹ️  Updated: [{object_id}] {name} → {route}")
                )

        # Display summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Total pages defined: {len(pages_to_create)}")
        self.stdout.write(f"New pages created: {created_count}")
        self.stdout.write(f"Existing pages updated: {updated_count}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("PAGES BY MODULE"))
        self.stdout.write("=" * 80)

        # Group by module
        from collections import defaultdict

        modules = defaultdict(list)
        for object_id, name, module_code, description, route in pages_to_create:
            modules[module_code].append(f"  • {name} (ID: {object_id})")

        for module, pages in sorted(modules.items()):
            self.stdout.write(f"\n{module.upper()}:")
            for page in pages:
                self.stdout.write(page)

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Page objects populated successfully!"))
        self.stdout.write("=" * 80 + "\n")
