from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context
from django_tenants.models import TenantMixin

from financials.models import G_LAccount


@transaction.atomic
def ensure_mobile_money_account() -> dict:
    """Create or update the Mobile Money Accounts GL account."""
    account_data = {
        "no": "2930",
        "name": "Mobile Money Accounts",
        "indentation": 3,
        "income_balance": "Balance Sheet",
        "accountcategory": "Assets",
        "debit_credit": "Both",
        "accounttype": "Posting",
        "totaling": None,
        "direct_posting": False,
        "blocked": False,
    }

    account, created = G_LAccount.objects.get_or_create(
        no=account_data["no"],
        defaults=account_data,
    )

    if created:
        return {"action": "created", "account": account}
    
    # Update if it exists but fields differ
    changed_fields = []
    for field_name, value in account_data.items():
        if field_name == "no":  # Skip primary key
            continue
        if getattr(account, field_name) != value:
            setattr(account, field_name, value)
            changed_fields.append(field_name)
    
    if changed_fields:
        account.save(update_fields=changed_fields)
        return {"action": "updated", "account": account, "changed_fields": changed_fields}
    
    return {"action": "exists", "account": account}


class Command(BaseCommand):
    help = "Seed the Mobile Money Accounts GL account (2930)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="semuna",
            help="Schema name for tenant-specific operation (default: semuna)",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema", "semuna")
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS(f"SEEDING MOBILE MONEY ACCOUNT FOR SCHEMA: {schema_name}")
        )
        self.stdout.write("=" * 80 + "\n")

        try:
            with schema_context(schema_name):
                result = ensure_mobile_money_account()
                account = result["account"]
                
                if result["action"] == "created":
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Created GL Account: {account.no} - {account.name}"
                        )
                    )
                elif result["action"] == "updated":
                    changed = ", ".join(result["changed_fields"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Updated GL Account: {account.no} - {account.name} "
                            f"(changed: {changed})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ GL Account already exists: {account.no} - {account.name}"
                        )
                    )
                
                self.stdout.write(f"\n  Account Details:")
                self.stdout.write(f"    No.: {account.no}")
                self.stdout.write(f"    Name: {account.name}")
                self.stdout.write(f"    Type: {account.accounttype}")
                self.stdout.write(f"    Category: {account.accountcategory}")
                self.stdout.write(f"    Income/Balance: {account.income_balance}")
                self.stdout.write(f"    Indentation: {account.indentation}")
                self.stdout.write(f"    Direct Posting: {account.direct_posting}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error seeding account: {str(e)}")
            )
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("MOBILE MONEY ACCOUNT SEEDING COMPLETED"))
        self.stdout.write("=" * 80 + "\n")

