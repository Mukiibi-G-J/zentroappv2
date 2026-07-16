# Company creation performance

## Measuring where time goes

`create_company_task` emits structured log lines:

```text
company_creation_timing phase=<name> elapsed_total_s=<s> phase_delta_s=<s>
```

Phases (in order):

| Phase | Meaning |
| --- | --- |
| `validation_complete` | Request payload validated |
| `company_and_domain_created` | `Company` + `Domain` saved (clone from `_zentro_template` or slow migrations) |
| `after_admin_user_bootstrap` | Admin user, branch dimension, location |
| `after_roles_permissions_user_groups` | Roles/permissions/user groups (skipped when template is pre-seeded) |
| `after_tenant_json_import` | JSON baseline import (skipped when template is pre-seeded) |
| `after_number_series_and_defaults` | Company-specific vendor/customer + inventory posting sync |
| `completed` | Main task finished (SMS and completion email are queued separately) |

**How to record a baseline:** run one signup (staging or local with Celery + Redis), then search worker logs for `company_creation_timing`. The largest `phase_delta_s` indicates the bottleneck. With a pre-seeded template, roles/import phases should be near-zero.

## Fast path (recommended)

1. Keep `_zentro_template` rebuilt and **pre-seeded**: `python manage.py rebuild_template_schema`
2. Verify: `python manage.py verify_template_schema` (checks migrations **and** baseline rows)
3. Signup clones structure + baseline; `create_company_task` only creates admin + company-specific rows

Shared bootstrap lives in `company/tenant_baseline.py` (`run_tenant_baseline_bootstrap`).

## If migrations dominate (template missing)

- Run `rebuild_template_schema` so signups stop falling back to per-tenant migrations.
- **Squash migrations** (Django) for apps that are stable, to reduce rebuild time.

## If post-clone bootstrap still runs

- Template exists but was built **before** pre-seed support → `tenant_has_baseline_data()` is false → full seed runs every signup. Rebuild once.

## Celery workers

- **Windows (development):** `settings.py` sets `CELERY_WORKER_POOL = "solo"` and `CELERY_WORKER_CONCURRENCY = 1` because prefork is problematic on Windows. Only one long-running task at a time per worker process.
- **Linux (production):** run workers with a multi-process pool, for example:

  `celery -A core worker --pool=prefork --concurrency=4`

  Tune `concurrency` to CPU/DB capacity. Long tasks such as `create_company_task` benefit from not sharing one solo worker with everything else (dedicated queue/worker is optional).

## Async notifications

Admin SMS and the “account ready” email are sent via `send_company_creation_admin_sms_task` and `send_company_creation_completion_email_task` so they do not block task completion.

## Tenant JSON import

`company.tenant_import.run_tenant_data_import` performs the same work as `manage.py import_tenant_data` without reading the JSON file twice during onboarding.
