#!/usr/bin/env python
"""
Script to update existing payment methods to set NOT_PAID to not require amount received
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


def update_payment_methods_requires_amount():
    """Update existing payment methods to set NOT_PAID to not require amount received"""
    try:
        print("Updating payment methods requires_amount_received settings...")

        # Update NOT_PAID payment method to not require amount received
        not_paid_method = PaymentMethod.objects.filter(code="NOT_PAID").first()
        if not_paid_method:
            not_paid_method.requires_amount_received = False
            not_paid_method.save()
            print(
                f"Updated {not_paid_method.code} - {not_paid_method.description}: requires_amount_received = False"
            )
        else:
            print("NOT_PAID payment method not found")

        # List all payment methods and their current settings
        print("\nCurrent payment method settings:")
        for method in PaymentMethod.objects.all():
            print(
                f"  {method.code} - {method.description}: requires_amount_received = {method.requires_amount_received}"
            )

        print("\nPayment methods updated successfully!")

    except Exception as e:
        print(f"Error updating payment methods: {str(e)}")


if __name__ == "__main__":
    update_payment_methods_requires_amount()
