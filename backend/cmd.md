1. python manage.py loaddata data/business_objectives.json
2. python manage.py loaddata data/business_categories.json
3. python manage.py seed_roles

4. python manage.py loaddata data/smtp_setup.json
5. python manage.py delete_migrations
   python manage.py populate_objects_table
   python manage.py migrate sales zero
   python manage.py migrate --fake
   python manage.py migrate_schemas

6. rm -rf env/Lib/site-packages/django/contrib/sessions/migrations/[0-9]\*.py
7. python manage.py delete_migrations --exclude=items

python manage.py loaddata data/business_objectives.json && python manage.py loaddata data/business_categories.json && python manage.py loaddata data/pricing_plans.json --settings=core.settingsprod

python manage.py loaddata data/business_objectives.json --settings=core.settingsprod && \
python manage.py loaddata data/business_categories.json --settings=core.settingsprod && \
python manage.py loaddata data/pricing_plans.json --settings=core.settingsprod
python manage.py setup_starter_offers --settings=core.settingsprod

python manage.py create_tenant --name="semuna" --schema_name="semuna" --domain-domain="semuna.zentroapp.app" --domain-is_primary=true

celery commands

# For Windows development - use solo pool to avoid permission errors

celery -A core worker --pool=solo --loglevel=info

# Use prefork pool (default) for better handling of time.sleep() and state updates

celery -A core worker --loglevel=info

# For Linux/Mac production - use prefork pool for better performance

celery -A core worker --pool=eventlet --loglevel=info

# Use prefork pool (default) for better handling of time.sleep() and state updates

# celery -A core worker --loglevel=info

# celery beat commands
# Code-based schedules: use default Celery beat (CELERY_BEAT_SCHEDULE in settings). Do not use DatabaseScheduler or PeriodicTask for backups.
celery -A core beat -l info

# Legacy django-celery-beat DB schedules (ignored if you rely on CELERY_BEAT_SCHEDULE above):
# celery -A core beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Bare metal / VPS (no Docker) — database backups to S3
# - Install pg_dump on the host that runs the Celery *worker* (not only the web app):
#   e.g. Ubuntu: `sudo apt install postgresql-client`
# - Run both processes from `zentro-backend` with the same venv and settings as gunicorn, e.g.:
#   `source ../env/bin/activate`
#   `export DJANGO_SETTINGS_MODULE=core.settingsprod`   # or pass --settings on manage.py only
#   `celery -A core worker --loglevel=info`
#   `celery -A core beat -l info`                      # separate terminal or systemd unit
# - Scheduled backups use CELERY_BEAT_SCHEDULE in settings (daily 02:00 UTC, weekly Sun 03:00 UTC).
# - Backups are pg_dump custom format (.dump, same as `pg_dump -F c`); restore with pg_restore, not psql.
# - On-demand: `python manage.py run_backup --settings=core.settingsprod` (or `--sync` for a blocking run).
# The Docker-based `celery-beat` service in compose files is optional; skip it if you do not use Docker.

# --- Supervisor (VPS / bare metal, same host as zentro + zentro-celery) ---
# Example program file (adjust paths, then copy to conf.d):
#   zentro-backend/deploy/supervisor/zentro-celery-beat.conf.example  ->  /etc/supervisor/conf.d/zentro-celery-beat.conf
#
#   sudo supervisorctl reread
#   sudo supervisorctl update
#   sudo supervisorctl status
#   sudo supervisorctl restart zentro
#   sudo supervisorctl restart zentro-celery
#   sudo supervisorctl restart zentro-celery-beat
#   sudo supervisorctl restart zentro-flower
#
# First-time after adding the program: `supervisorctl start zentro-celery-beat` (or rely on autostart=true after update).

flower commands
celery -A core.celery_app flower
celery -A core.celery_app flower --basic_auth=jom:K@tende1
celery -A core.celery_app flower --basic_auth=jom:K@tende1 --port=$PORT

docker commands

    docker build -t core:latest .
        t->meaing tag
    docker run -d -p 8000:8000 core:latest
       d->meaing demo mode
       p->meaing port

docker login -u AWS -p $(aws ecr get-login-password --region us-east-2) 311377958566.dkr.ecr.us-east-2.amazonaws.com

docker push 311377958566.dkr.ecr.us-east-2.amazonaws.com/zentro-backend:latest

PS C:\Users\JOM> aws ecr describe-repositories --repository-name zentro-backend
{
"repositories": [
{
"repositoryArn": "arn:aws:ecr:us-east-2:311377958566:repository/zentro-backend",
"registryId": "311377958566",
"repositoryName": "zentro-backend",
"repositoryUri": "311377958566.dkr.ecr.us-east-2.amazonaws.com/zentro-backend",
"createdAt": "2025-02-02T06:44:31.067000+03:00",
"imageTagMutability": "MUTABLE",
"imageScanningConfiguration": {
"scanOnPush": false
},
"encryptionConfiguration": {
"encryptionType": "AES256"
}
}
]
}

aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 311377958566.dkr.ecr.us-east-2.amazonaws.com

ssh -i "C:\Users\JOM\Downloads\zentroapp-django.pem" ubuntu@<your-ec2-ip>

docker exec -it <container_name_or_id> bash

1. First, fake rollback the conflicting migration:

```bash
python manage.py migrate config_packages zero --fake
```

python manage.py migrate --settings=core.settingsprod

python manage.py seed_roles --tenant="semuna" --settings=core.settingsprod

python manage.py tenant_command fix_posting_dates --schema=daurice

# Fix user dimension_1 when it has string codes (e.g. "Kyengera") instead of integer IDs (ValidationError on admin login)
python manage.py tenant_command fix_user_dimension_1 --schema=semuna
python manage.py tenant_command fix_user_dimension_1 --schema=semuna --dry-run

python manage.py tenant_command seed_sales_order_numbers --schema=hardwareworld

python manage.py migrate --settings=core.settingsprod
python manage.py makemigrations --settings=core.settingsprod

python manage.py makemigrations `  financials`
sales `  items`
settings `  config_packages`
postings `  purchases`
payments `  expenses`
reports `  resources`
production

from financials.models import GeneralLedgerEntry, G_LAccount
from django.db.models import Sum

# 1) Is the entire general ledger balanced?

GeneralLedgerEntry.objects.aggregate(total=Sum("amount"))

python manage.py tenant_command setup_page_permissions --schema=nema

Mobile Settings API (React Native)

Endpoint:
- GET /api/settings/mobile/
- PATCH /api/settings/mobile/

Response shape:
{
  "searchMode": "barcode",
  "barcodeScannerEnabled": true,
  "barcodeBeepEnabled": true,
  "printer": {
    "type": "sunmi|bluetooth|none",
    "deviceName": "",
    "macAddress": "",
    "paperWidth": "58|80",
    "copies": 1
  },
  "tenant": {
    "currentTenant": "schema_name"
  },
  "updatedAt": "ISO_DATE"
}

Validation rules:
- searchMode: barcode|realtime
- boolean flags must be strict JSON booleans
- printer.type:
  - none: deviceName and macAddress are cleared
  - sunmi: paperWidth in 58|80 and copies >= 1
  - bluetooth: requires deviceName and valid MAC address (AA:BB:CC:DD:EE:FF)

Concurrency:
- Use If-Unmodified-Since header with last updatedAt value.
- If stale, API returns 409 with:
  { "code": "settings_conflict", "message": "...", "details": { "currentUpdatedAt": "..." } }

Error format:
- { "code": "...", "message": "...", "details": {...} }

Sample curl:

curl -X GET "http://localhost:8000/api/settings/mobile/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "X-Tenant: <schema_name>"

curl -X PATCH "http://localhost:8000/api/settings/mobile/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "X-Tenant: <schema_name>" \
  -H "Content-Type: application/json" \
  -H "If-Unmodified-Since: 2026-03-26T16:00:00Z" \
  -d '{
    "searchMode": "realtime",
    "barcodeScannerEnabled": false,
    "barcodeBeepEnabled": true,
    "printer": {
      "type": "bluetooth",
      "deviceName": "Zebra M2",
      "macAddress": "AA:BB:CC:DD:EE:FF",
      "paperWidth": "58",
      "copies": 1
    }
  }'
