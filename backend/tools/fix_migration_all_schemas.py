import os
import sys

# Ensure project root (zentro-backend) is on sys.path so that 'core' is importable
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_LANGUAGE", "en-us")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # type: ignore
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django_tenants.utils import get_tenant_model, schema_context


def main():
    # Usage: python tools/fix_migration_all_schemas.py action app_label migration_name
    # action: 'apply' or 'unapply'
    if len(sys.argv) != 4:
        print("Usage: python tools/fix_migration_all_schemas.py <apply|unapply> <app_label> <migration_name>")
        sys.exit(1)

    action = sys.argv[1]
    app_label = sys.argv[2]
    migration_name = sys.argv[3]

    django.setup()
    
    # Fix public schema
    print(f"\nFixing public schema...")
    conn = connections["default"]
    recorder = MigrationRecorder(conn)
    recorder.ensure_schema()
    
    try:
        if action == "apply":
            recorder.record_applied(app_label, migration_name)
            print(f"  ✓ Marked {app_label}.{migration_name} as applied on public")
        elif action == "unapply":
            recorder.record_unapplied(app_label, migration_name)
            print(f"  ✓ Marked {app_label}.{migration_name} as UN-applied on public")
    except Exception as exc:
        print(f"  ✗ Error on public: {exc}")
    
    # Fix all tenant schemas
    TenantModel = get_tenant_model()
    tenants = TenantModel.objects.exclude(schema_name="public")
    
    print(f"\nFixing {tenants.count()} tenant schemas...")
    success_count = 0
    error_count = 0
    
    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                # Get connection for this schema
                from django.db import connection
                recorder = MigrationRecorder(connection)
                recorder.ensure_schema()
                
                if action == "apply":
                    recorder.record_applied(app_label, migration_name)
                    print(f"  ✓ {tenant.schema_name}: Marked {app_label}.{migration_name} as applied")
                    success_count += 1
                elif action == "unapply":
                    recorder.record_unapplied(app_label, migration_name)
                    print(f"  ✓ {tenant.schema_name}: Marked {app_label}.{migration_name} as UN-applied")
                    success_count += 1
        except Exception as exc:
            print(f"  ✗ {tenant.schema_name}: Error - {exc}")
            error_count += 1
    
    print(f"\nSummary: {success_count} successful, {error_count} errors")


if __name__ == "__main__":
    main()

