from django.core.management.base import BaseCommand
from django.db import transaction
from financials.models import G_LAccount
from bank_account.models import BankAccount, BankAccountPostingGroup


@transaction.atomic
def ensure_mobile_money_bank_accounts():
    """Create or update MTN_MONEY and AIRTEL_MONEY bank accounts with posting groups"""
    
    # First, ensure Mobile Money G/L Account exists (2930)
    try:
        mobile_money_gl_account = G_LAccount.objects.get(no="2930")
    except G_LAccount.DoesNotExist:
        raise Exception(
            "Mobile Money G/L Account (2930) does not exist. "
            "Please run 'seed_mobile_money_account' command first."
        )
    
    # Create or get Mobile Money Posting Group
    posting_group, created = BankAccountPostingGroup.objects.get_or_create(
        code="MOBILE_MONEY",
        defaults={
            "description": "Mobile Money",
            "bank_account": mobile_money_gl_account,
        }
    )
    
    # Update posting group if G/L account is not set
    if not posting_group.bank_account:
        posting_group.bank_account = mobile_money_gl_account
        posting_group.save(update_fields=["bank_account"])
    
    # Create MTN_MONEY bank account
    mtn_account, mtn_created = BankAccount.objects.get_or_create(
        no="MTN_MONEY",
        defaults={
            "name": "MTN Money",
            "bank_account_posting_group": posting_group,
        }
    )
    
    # Update MTN account if posting group is not set
    if not mtn_account.bank_account_posting_group:
        mtn_account.bank_account_posting_group = posting_group
        mtn_account.save(update_fields=["bank_account_posting_group"])
    
    # Create AIRTEL_MONEY bank account
    airtel_account, airtel_created = BankAccount.objects.get_or_create(
        no="AIRTEL_MONEY",
        defaults={
            "name": "Airtel Money",
            "bank_account_posting_group": posting_group,
        }
    )
    
    # Update Airtel account if posting group is not set
    if not airtel_account.bank_account_posting_group:
        airtel_account.bank_account_posting_group = posting_group
        airtel_account.save(update_fields=["bank_account_posting_group"])
    
    return {
        "posting_group": posting_group,
        "posting_group_created": created,
        "mtn_account": mtn_account,
        "mtn_created": mtn_created,
        "airtel_account": airtel_account,
        "airtel_created": airtel_created,
    }


class Command(BaseCommand):
    help = "Create MTN_MONEY and AIRTEL_MONEY bank accounts with posting groups"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS("SEEDING MOBILE MONEY BANK ACCOUNTS")
        )
        self.stdout.write("=" * 80 + "\n")

        try:
            result = ensure_mobile_money_bank_accounts()
            
            # Report posting group status
            if result["posting_group_created"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created Bank Account Posting Group: {result['posting_group'].code} - {result['posting_group'].description}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Found Bank Account Posting Group: {result['posting_group'].code} - {result['posting_group'].description}"
                    )
                )
            
            # Report MTN account status
            if result["mtn_created"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created Bank Account: {result['mtn_account'].no} - {result['mtn_account'].name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Found Bank Account: {result['mtn_account'].no} - {result['mtn_account'].name}"
                    )
                )
            
            # Report Airtel account status
            if result["airtel_created"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created Bank Account: {result['airtel_account'].no} - {result['airtel_account'].name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Found Bank Account: {result['airtel_account'].no} - {result['airtel_account'].name}"
                    )
                )
            
            self.stdout.write(f"\n  Posting Group: {result['posting_group'].code}")
            self.stdout.write(f"  G/L Account: {result['posting_group'].bank_account.no if result['posting_group'].bank_account else 'Not set'}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error seeding bank accounts: {str(e)}")
            )
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("MOBILE MONEY BANK ACCOUNTS SEEDING COMPLETED"))
        self.stdout.write("=" * 80 + "\n")

