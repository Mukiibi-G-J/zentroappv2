"""
Quick script to enable restaurant module for a company
Usage: python enable_restaurant_module.py <schema_name>
"""
import os
import django
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django_tenants.utils import schema_context
from company.models import Company
from utils.modules import ensure_base_modules

def enable_restaurant_module(schema_name):
    """Enable restaurant module for a company"""
    with schema_context(schema_context('public') if schema_name == 'public' else schema_name):
        # Get company from public schema
        from django_tenants.utils import get_public_schema_name
        public_schema = get_public_schema_name()
        
        with schema_context(public_schema):
            try:
                company = Company.objects.get(schema_name=schema_name)
                current_modules = company.enabled_modules or ["pos"]
                
                if "restaurant" not in current_modules:
                    current_modules.append("restaurant")
                    # Ensure base modules are included and POS is first
                    company.enabled_modules = ensure_base_modules(current_modules)
                    company.save()
                    print(f"✅ Restaurant module enabled for company: {company.name} (schema: {schema_name})")
                    print(f"   Enabled modules: {company.enabled_modules}")
                else:
                    print(f"ℹ️  Restaurant module is already enabled for company: {company.name}")
                    print(f"   Enabled modules: {company.enabled_modules}")
            except Company.DoesNotExist:
                print(f"❌ Company with schema '{schema_name}' not found")
                print("Available companies:")
                for c in Company.objects.all():
                    print(f"  - {c.name} (schema: {c.schema_name})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python enable_restaurant_module.py <schema_name>")
        print("\nTo find your schema name, check the Company model in Django admin")
        sys.exit(1)
    
    schema_name = sys.argv[1]
    enable_restaurant_module(schema_name)



