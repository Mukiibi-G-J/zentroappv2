from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context
from django_tenants.models import Tenant

class Command(BaseCommand):
    help = 'Applies config_packages migrations to all tenants'

    def handle(self, *args, **options):
        from django.core.management import call_command
        
        # Get all tenants
        tenants = Tenant.objects.all()
        
        for tenant in tenants:
            self.stdout.write(f"Migrating tenant: {tenant.schema_name}")
            with tenant_context(tenant):
                # Apply migrations for config_packages
                call_command('migrate', 'config_packages') 