# Golden tenant template (`_zentro_template`)

New companies normally get their PostgreSQL schema by **cloning** `_zentro_template` instead of replaying every tenant migration. That keeps signup fast (milliseconds vs minutes).

## First-time and after migration changes

```bash
python manage.py rebuild_template_schema
```

This drops `_zentro_template` (if present), recreates it with full tenant migrations, then deletes the throwaway `Company` row so the template schema is **not** linked in `public.company_company`.

## Automatic rebuild (local / deploy scripts)

After **tenant** migrations run, the `company` app sets a flag when `post_migrate` reports a non-empty plan on a **non-public** schema. On **process exit**, it runs `rebuild_template_schema` once so the template stays aligned with migration history.

Disable that behavior (e.g. CI that migrates then verifies separately):

```bash
export DISABLE_TEMPLATE_REBUILD=1
```

## Verify template freshness (CI)

```bash
python manage.py verify_template_schema
```

- Exit code **0**: `_zentro_template` exists and has **no pending migrations** (checked via Django’s `MigrationExecutor` on that schema).
- Exit code **1**: missing or stale.

**Note:** Comparing `django_migrations` row counts between `_zentro_template` and `public` is not meaningful in django-tenants (different app sets on shared vs tenant). The verify command uses pending-migration detection instead.

### Suggested CI flow

1. Run migrations (with `DISABLE_TEMPLATE_REBUILD=1` if you do not want an atexit rebuild in that job).
2. Run `python manage.py rebuild_template_schema` once after tenant migrations (or rely on atexit when the flag is unset).
3. Run `python manage.py verify_template_schema` and fail the job on non-zero exit.

## Operations

- `_zentro_template` must **never** remain as a row in `public.company_company` after a successful rebuild.
- Concurrent signups use different destination schema names; `clone_schema` refuses an existing destination schema.
- If `_zentro_template` is missing, `Company.save` logs a warning and falls back to **per-tenant migrations** (`auto_create_schema=True` on that instance) so fresh dev checkouts still work until someone runs `rebuild_template_schema`.
