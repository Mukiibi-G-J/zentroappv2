# Golden tenant template (`_zentro_template`)

New companies normally get their PostgreSQL schema by **cloning** `_zentro_template` instead of replaying every tenant migration. That keeps signup fast (milliseconds vs minutes).

The template is **pre-seeded** during rebuild with tenant-generic baseline data:

- Default roles, role centres, user groups
- Pages engine (`seed_pages`) + Zentro page IDs (PageId == ObjectId)
- Permission sets (`setup_page_permissions`)
- Chart of accounts / posting groups (JSON import) and related seeds
- Financial reports (`seed_income_statement_row_definition` — INCOME P&L + MONTHLY columns; required by `tenant_has_baseline_data`)
- Number series + PurchasePayable / SalesReceivable setup

Signup then clones that data and only adds company-specific rows (admin user, domain, location contact fields, General vendor/customer, subscription).

## First-time and after migration changes

```bash
python manage.py rebuild_template_schema
```

This drops `_zentro_template` (if present), recreates it with full tenant migrations, **runs baseline bootstrap**, then deletes the throwaway `Company` row so the template schema is **not** linked in `public.company_company`.

**Note:** Rebuild is slower than before (migrations + full seed once). Each signup is much faster when cloning the seeded template.

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

- Exit code **0**: `_zentro_template` exists, has **no pending migrations**, and has **baseline data** (roles, pages, permission sets, number series).
- Exit code **1**: missing, stale migrations, or empty (unseeded) template.

**Note:** Comparing `django_migrations` row counts between `_zentro_template` and `public` is not meaningful in django-tenants (different app sets on shared vs tenant). The verify command uses pending-migration detection instead.

### Suggested CI flow

1. Run migrations (with `DISABLE_TEMPLATE_REBUILD=1` if you do not want an atexit rebuild in that job).
2. Run `python manage.py rebuild_template_schema` once after tenant migrations (or rely on atexit when the flag is unset).
3. Run `python manage.py verify_template_schema` and fail the job on non-zero exit.

## Operations

- `_zentro_template` must **never** remain as a row in `public.company_company` after a successful rebuild.
- Concurrent signups use different destination schema names; `clone_schema` refuses an existing destination schema.
- If `_zentro_template` is missing, `Company.save` logs a warning and falls back to **per-tenant migrations** (`auto_create_schema=True` on that instance) so fresh dev checkouts still work until someone runs `rebuild_template_schema`.
