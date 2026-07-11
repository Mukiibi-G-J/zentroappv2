import os
import sys
import datetime

# Ensure project root (zentro-backend) is on sys.path so that 'core' is importable
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BASE_DIR not in sys.argv:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_LANGUAGE", "en-us")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # type: ignore
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder


def main():
    # Usage: python tools/fix_migration_public.py action app_label migration_name
    # action: 'apply' or 'unapply'
    if len(sys.argv) != 4:
        print("Usage: python tools/fix_migration_public.py <apply|unapply> <app_label> <migration_name>")
        sys.exit(1)

    action = sys.argv[1]
    app_label = sys.argv[2]
    migration_name = sys.argv[3]

    django.setup()
    conn = connections["default"]
    recorder = new_recorder(conn)

    if action == "apply":
        recorder.record_applied(app_label, migration_name)
        print(f"Marked {app_label}.{migration_name} as applied on public (default)")
    elif action == "unapply":
        try:
            recorder.record_unapplied(app_label, migration_name)
            print(f"Marked {app_label}.{migration_name} as UN-applied on public (default)")
        except Exception as exc:
            print(f"Error during record_unapplied: {exc}")
            sys.exit(1)
    else:
        print("Unknown action. Use 'apply' or 'unapply'.")
        sys.exit(1)


def new_recorder(conn):
    # Ensure the migrations table exists
    rec = MigrationRecorder(conn)
    rec.ensure_schema()
    return rec


if __name__ == "__main__":
    main()
