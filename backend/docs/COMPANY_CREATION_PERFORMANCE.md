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
| `company_and_domain_created` | `Company` + `Domain` saved (includes new tenant schema creation and **full migration run** via django-tenants) |
| `after_admin_user_bootstrap` | Admin user, branch dimension, location |
| `after_roles_permissions_user_groups` | Roles, management commands, user groups |
| `after_tenant_json_import` | JSON baseline import + `seed_prepayment_accounts` + subscription patch + inventory location update |
| `after_number_series_and_defaults` | Number series, default vendor/customer, branch reconcile |
| `completed` | Main task finished (SMS and completion email are queued separately) |

**How to record a baseline:** run one signup (staging or local with Celery + Redis), then search worker logs for `company_creation_timing`. The largest `phase_delta_s` indicates the bottleneck (usually `company_and_domain_created` if migrations dominate).

## If migrations dominate

- **Squash migrations** (Django) for apps that are stable, to reduce work per new tenant schema.
- **Template schema (advanced):** maintain a PostgreSQL schema that is already migrated (and optionally pre-seeded), then clone it for each new tenant instead of running the full migration chain. Requires updating the template on every deploy that changes migrations. Coordinate with django-tenants lifecycle (schema name rename or `CREATE SCHEMA ... WITH TEMPLATE` patterns).

## Celery workers

- **Windows (development):** `settings.py` sets `CELERY_WORKER_POOL = "solo"` and `CELERY_WORKER_CONCURRENCY = 1` because prefork is problematic on Windows. Only one long-running task at a time per worker process.
- **Linux (production):** run workers with a multi-process pool, for example:

  `celery -A core worker --pool=prefork --concurrency=4`

  Tune `concurrency` to CPU/DB capacity. Long tasks such as `create_company_task` benefit from not sharing one solo worker with everything else (dedicated queue/worker is optional).

## Async notifications

Admin SMS and the “account ready” email are sent via `send_company_creation_admin_sms_task` and `send_company_creation_completion_email_task` so they do not block task completion.

## Tenant JSON import

`company.tenant_import.run_tenant_data_import` performs the same work as `manage.py import_tenant_data` without reading the JSON file twice during onboarding.
