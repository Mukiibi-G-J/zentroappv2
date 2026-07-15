#!/usr/bin/env python
"""
Script to create default payment methods for sales
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from financials.models import PaymentMethod
from financials.enums import BalacingAccountType
from bank_account.models import BankAccount


def create_default_payment_methods():
    """Create default payment methods if they don't exist"""
    try:
        print("Creating default payment methods...")

        # Get bank accounts if they exist (they should be created during company creation)
        airtel_bank_account = None
        mtn_bank_account = None
        try:
            airtel_bank_account = BankAccount.objects.get(no="AIRTEL_MONEY")
        except BankAccount.DoesNotExist:
            print("Warning: AIRTEL_MONEY bank account not found. Skipping Airtel Money payment method.")
        
        try:
            mtn_bank_account = BankAccount.objects.get(no="MTN_MONEY")
        except BankAccount.DoesNotExist:
            print("Warning: MTN_MONEY bank account not found. Skipping MTN Money payment method.")

        # Define default payment methods
        default_methods = [
            {
                "code": "CASH",
                "description": "Cash",
                "bal_account_type": BalacingAccountType.GLAccount.value,
                "requires_amount_received": True,
            },
        ]
        
        # Add mobile money payment methods only if bank accounts exist
        if airtel_bank_account:
            default_methods.append({
                "code": "AIRTEL_MONEY",
                "description": "Airtel Money",
                "bal_account_type": BalacingAccountType.Bank_Account.value,
                "bal_bank_account_no": airtel_bank_account,
                "requires_amount_received": True,
            })
        
        if mtn_bank_account:
            default_methods.append({
                "code": "MTN_MONEY",
                "description": "MTN Money",
                "bal_account_type": BalacingAccountType.Bank_Account.value,
                "bal_bank_account_no": mtn_bank_account,
                "requires_amount_received": True,
            })

        default_methods.extend(
            [
                {
                    "code": "DEBIT",
                    "description": "Debit Card",
                    "bal_account_type": BalacingAccountType.GLAccount.value,
                    "requires_amount_received": True,
                },
                {
                    "code": "NOT_PAID",
                    "description": "Not Paid Yet",
                    "bal_account_type": BalacingAccountType.GLAccount.value,
                    "requires_amount_received": False,
                },
            ]
        )

        created_count = 0
        for method_data in default_methods:
            payment_method, created = PaymentMethod.objects.get_or_create(
                code=method_data["code"], defaults=method_data
            )

            if created:
                print(
                    f"Created payment method: {payment_method.code} - {payment_method.description}"
                )
                created_count += 1
            else:
                print(
                    f"Payment method already exists: {payment_method.code} - {payment_method.description}"
                )

        print(f"\nTotal payment methods created: {created_count}")
        print("Default payment methods setup completed!")

        # List all existing payment methods
        print("\nAll payment methods:")
        all_methods = PaymentMethod.objects.all().order_by("code")
        for method in all_methods:
            print(f"  {method.code} - {method.description}")

    except Exception as e:
        print(f"Error creating payment methods: {e}")


if __name__ == "__main__":
    create_default_payment_methods()
