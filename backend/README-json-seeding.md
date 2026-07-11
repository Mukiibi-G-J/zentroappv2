### JSON-based export & reseed (public + primewise)

#### Overview

- **Goal**: move all useful data from production DB into **JSON fixtures** for:
  - `public` schema (shared apps)
  - `primewise` tenant schema (tenant apps)
- Then on a fresh local DB:
  - run migrations
  - **seed** data via `loaddata` (no manual SQL hacking)

---

### 1. Public schema → JSON

From the server:

```bash
cd /root/projects/zentro-app/zentro-backend

python manage.py dumpdata \
  company dimension home setup common base \
  --exclude contenttypes \
  --exclude auth.Permission \
  --exclude admin.LogEntry \
  --exclude sessions.Session \
  --indent 2 \
  --output dumps/public.json \
  --settings=core.settingsprod
```

- Result: `dumps/public.json` – Django fixture with public data.

---

### 2. Primewise schema → JSON (per app)

Custom command: `company/management/commands/export_primewise_json.py`.

Runs inside `schema_context('primewise')` and:

- iterates **per app & per model**
- skips system models (`contenttypes`, `Permission`, `Session`, `LogEntry`)
- skips models whose **tables are missing** or whose schema is broken
- serializes everything else to JSON fixtures

Run it:

```bash
cd /root/projects/zentro-app
source env/bin/activate
cd zentro-backend

python manage.py export_primewise_json \
  --schema primewise \
  --output-dir dumps/primewise-json \
  --settings=core.settingsprod
```

It prints what it exports and what it skips. Example files in `dumps/primewise-json/`:

- `primewise_permissions.json`
- `primewise_dimension.json`
- `primewise_authentication.json`
- `primewise_financials.json`
- `primewise_sales.json`
- `primewise_items.json`
- `primewise_setup.json`
- `primewise_config_packages.json`
- `primewise_postings.json`
- `primewise_purchases.json`

Apps/models with no data or missing tables are reported and skipped (e.g. parts of `settings`, `reports`, `resources`, `hotel_management`, `restaurant_management`, some VAT/phys inventory tables, etc.).

Each file is a standard Django fixture: JSON list of objects with `model`, `pk`, `fields`.

---

### 3. Create fresh local DB and run migrations

On local machine:

1. Create DB (example):

   ```bash
   createdb zentroapp_db_local
   ```

2. Point `DATABASES["default"]` to this DB (via `.env` / settings).
3. Apply public + tenant migrations:

   ```bash
   cd /path/to/local/zentro-backend
   python manage.py migrate --settings=core.settingsprod
   ```

4. Create `primewise` tenant + domain:

   ```bash
   python manage.py shell --settings=core.settingsprod
   ```

   ```python
   from company.models import Company, Domain

   tenant = Company.objects.create(
       name="Primewise",
       domain_url="primewise.local",
       schema_name="primewise",
       address="",
       email="",
       phone="",
   )
   Domain.objects.create(
       domain="primewise.local",
       tenant=tenant,
       is_primary=True,
   )
   ```

5. Run tenant migrations (depending on your setup, e.g.):

   ```bash
   python manage.py migrate_schemas --settings=core.settingsprod
   ```

---

### 4. Seed public data (local)

Copy `dumps/public.json` from server → local backend, then:

```bash
cd /path/to/local/zentro-backend

python manage.py loaddata dumps/public.json --settings=core.settingsprod
```

---

### 5. Seed primewise data (local)

Copy whole `dumps/primewise-json/` directory from server → local.

Then load key app fixtures into `primewise`:

```bash
python manage.py tenant_command loaddata \
  --schema=primewise \
  dumps/primewise-json/primewise_permissions.json \
  dumps/primewise-json/primewise_dimension.json \
  dumps/primewise-json/primewise_authentication.json \
  dumps/primewise-json/primewise_financials.json \
  dumps/primewise-json/primewise_sales.json \
  dumps/primewise-json/primewise_items.json \
  dumps/primewise-json/primewise_setup.json \
  dumps/primewise-json/primewise_config_packages.json \
  dumps/primewise-json/primewise_postings.json \
  dumps/primewise-json/primewise_purchases.json \
  --settings=core.settingsprod
```

Adjust the list of JSON files based on what you actually exported and want to seed.

---

### 6. Sanity checks

- Access local `primewise` tenant (e.g. `http://primewise.local:8000/`).
- Verify:
  - master data exists (items, customers, GL accounts, etc.)
  - transactional data appears (sales/purchases, ledger entries)
  - dashboards/reports load without missing-FK errors.

---

### 7. SQL backups (optional safety net)

In addition to JSON, you also have full schema+data SQL dumps:

```bash
# On server
cd /root/projects/zentro-app/zentro-backend
export PGPASSWORD='K@tende1'

# public schema
pg_dump -h localhost -p 5432 -U jom -d zentroapp_db \
  -n public --no-owner --no-acl -F p \
  -f dumps/public_schema.sql

# primewise schema
pg_dump -h localhost -p 5432 -U jom -d zentroapp_db \
  -n primewise --no-owner --no-acl -F p \
  -f dumps/primewise_schema.sql
```

These give you an exact DB restore path if ever needed, alongside the JSON-based seeding flow above.

