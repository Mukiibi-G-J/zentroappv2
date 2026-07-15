#!/usr/bin/env python
"""
Test script to verify payment journal posting fix
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from payments.admin import PaymentJournalProcessor
from payments.models import PaymentJournal
from sales.models import Customer, CustomerPostingGroup
from financials.models import G_LAccount
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django_tenants.utils import tenant_context
from company.models import Company

def test_payment_journal_processor():
    """Test the PaymentJournalProcessor with customer payment"""
    
    # Get the ekk tenant
    try:
        tenant = Company.objects.filter(schema_name="ekk").first()
        if not tenant:
            print("❌ Tenant 'ekk' not found")
            return False
        print(f"✅ Using tenant: {tenant.name} (schema: {tenant.schema_name})")
    except Exception as e:
        print(f"❌ Error getting tenant: {e}")
        return False
    
    # Use tenant context
    with tenant_context(tenant):
        # Get existing data instead of creating new data
        try:
            # Get existing GL accounts
            receivables_account = G_LAccount.objects.filter(name__icontains="receivable").first()
            if not receivables_account:
                receivables_account = G_LAccount.objects.filter(accounttype="Asset").first()
            
            cash_account = G_LAccount.objects.filter(name__icontains="cash").first()
            if not cash_account:
                cash_account = G_LAccount.objects.filter(accounttype="Asset").first()
            
            if not receivables_account or not cash_account:
                print("❌ Could not find suitable GL accounts for testing")
                return False
            
            # Get existing customer posting group
            customer_posting_group = CustomerPostingGroup.objects.first()
            if not customer_posting_group:
                print("❌ Could not find customer posting group")
                return False
            
            # Get existing customer
            customer = Customer.objects.first()
            if not customer:
                print("❌ Could not find customer")
                return False
            
            # Update customer to have posting group if needed
            if not customer.customer_posting_group:
                customer.customer_posting_group = customer_posting_group
                customer.save()
            
            # Update posting group to have receivables account if needed
            if not customer_posting_group.receivables_account:
                customer_posting_group.receivables_account = receivables_account
                customer_posting_group.save()
            
            print(f"✅ Using existing data:")
            print(f"   Customer: {customer.name}")
            print(f"   Customer Posting Group: {customer_posting_group.code}")
            print(f"   Receivables Account: {receivables_account.name}")
            print(f"   Cash Account: {cash_account.name}")
            
            # Create a payment journal
            from datetime import date
            payment_journal = PaymentJournal.objects.create(
                document_no="PAY-TEST-001",
                posting_date=date(2025, 8, 31),
                account_type="Customer",
                account_no=customer,
                bal_account_type="G/L Account",
                bal_account_no=cash_account,
                amount=1000,
                description="Test payment"
            )
            
            # Create a mock request
            factory = RequestFactory()
            request = factory.get('/')
            request.user = get_user_model().objects.first()  # Get first user
            
            # Test the processor
            processor = PaymentJournalProcessor(payment_journal, request, "TEST-RCP-001")
            
            # Test validation first
            try:
                validation_result = processor._validate_payment_journal()
                print(f"✅ Validation passed: {validation_result}")
            except Exception as e:
                print(f"❌ Validation failed: {e}")
                return False
            
            entries = processor.process()
            
            print("✅ PaymentJournalProcessor test passed!")
            print(f"Generated {len(entries.get('gl_entries', []))} GL entries")
            print(f"Generated {len(entries.get('customer_entries', []))} Customer ledger entries")
            print(f"Generated {len(entries.get('detailed_customer_entries', []))} Detailed customer ledger entries")
            
            # Debug: Check what's in the processor
            print(f"Debug - Account type: {processor.payment_journal.account_type}")
            print(f"Debug - Account no: {processor.payment_journal.account_no}")
            print(f"Debug - Bal account type: {processor.payment_journal.bal_account_type}")
            print(f"Debug - Bal account no: {processor.payment_journal.bal_account_no}")
            print(f"Debug - Payables account: {processor.payables_account}")
            
            # Debug customer posting group
            customer = processor.payment_journal.account_no
            print(f"Debug - Customer posting group: {customer.customer_posting_group}")
            if customer.customer_posting_group:
                print(f"Debug - Customer posting group receivables account: {customer.customer_posting_group.receivables_account}")
            
            # Try to manually call _generate_gl_entries to see what happens
            try:
                transaction_no = f"PJ{processor.payment_journal.document_no}-{processor.payment_journal.posting_date.strftime('%Y%m%d')}-{processor.payment_journal.id}"
                processor._generate_gl_entries(transaction_no)
                print(f"✅ _generate_gl_entries completed successfully")
                print(f"Debug - GL entries count: {len(processor.gl_entries)}")
            except Exception as e:
                print(f"❌ _generate_gl_entries failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Check that GL entries have valid accounts
            for i, gl_entry in enumerate(entries.get('gl_entries', [])):
                if gl_entry['gl_account'] is None:
                    print(f"❌ GL entry {i} has null account: {gl_entry}")
                else:
                    print(f"✅ GL entry {i} has valid account: {gl_entry['gl_account']}")
            
            # Clean up test data
            payment_journal.delete()
                    
        except Exception as e:
            print(f"❌ PaymentJournalProcessor test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    print("Testing payment journal posting fix...")
    success = test_payment_journal_processor()
    if success:
        print("🎉 All tests passed! The fix should work.")
    else:
        print("💥 Tests failed. There might still be issues.")
