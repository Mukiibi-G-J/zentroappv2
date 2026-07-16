# ZentroApp → ZentroApp V2 — migration todos



**Single folder** for post-restore work when moving production from **zentroapp-web** to **zentroapp-webV2**.



Tick items per environment: **staging first**, then **production**.



---



## Start here (every prod DB restore)



**[00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)** — migrate / sequences / repairs. Run this **every time** you restore a dump.



**[11-restore-to-v2-ui-checklist.md](./11-restore-to-v2-ui-checklist.md)** — Role Centre, domains, Origin login, nginx JWT, subscription. **Required** if the Next.js frontend should work after restore (empty sidebar / wrong user without this).



---



## Todo index



| # | Todo | Status | Doc |

|---|------|--------|-----|

| 00 | **Restore production DB playbook (replay)** | 📋 Use every restore | [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md) |

| 01 | Payment ledger `applies_to_id` cleanup (Apply Entries / Preview Posting) | ☐ Production pending · ✅ Dev `primewise` | [01-payment-ledger-applies-to-id.md](./01-payment-ledger-applies-to-id.md) |

| 02 | Production DB migration run (shared + tenants) | ✅ Local prod restore · ☐ Production | [02-production-db-migration-run.md](./02-production-db-migration-run.md) |

| 03 | PostgreSQL sequence reset after `pg_restore` | ✅ Local · ☐ Production | [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md) |

| 04 | Schema drift: pages tables without migration rows (`motomoto` pattern) | ✅ Local `motomoto` · ☐ Production watch | [04-schema-drift-motomoto-pages.md](./04-schema-drift-motomoto-pages.md) |

| 05 | Unmigrated model changes (`makemigrations --check`) | ☐ Before go-live | [05-unmigrated-model-changes.md](./05-unmigrated-model-changes.md) |

| 06 | Migration history row count mismatch (cosmetic) | ℹ️ Documented | [06-migration-history-row-count.md](./06-migration-history-row-count.md) |

| 07 | Public schema: `authentication_customuser.system_id` missing (admin login) | ✅ Local `public` · ☐ Production | [07-public-schema-system-id.md](./07-public-schema-system-id.md) |
| 08 | **Primewise pilot → V2 ready** (migrate + seed_pages + page permissions) | ✅ Local `primewise` | [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md) |

| 09 | Pre-seeded `_zentro_template` (fast company creation) | ✅ Code · ☐ rebuild per env | [09-preseeded-zentro-template.md](./09-preseeded-zentro-template.md) |

| 10 | Safe `authentication.0020` DevicePushToken index rename (restore blocker) | ✅ Code · ✅ local | [10-auth-0020-safe-index-rename.md](./10-auth-0020-safe-index-rename.md) |

| 11 | **After restore → V2 web UI** (Role Centre, Origin tenant, nginx JWT, subscription) | 📋 Use every restore | [11-restore-to-v2-ui-checklist.md](./11-restore-to-v2-ui-checklist.md) |

| 12 | **Zentro page IDs** (PageId == ObjectId, 10xxx bands) | 📖 Reference | [12-page-id-vs-object-id.md](./12-page-id-vs-object-id.md) |



Add new todos as `13-….md` in **this folder** and link them in the table above.



---



## Standard order (every environment)



1. **Backup** production database (verify restore path).

2. **Follow** [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md) (migrate → sequences → repairs → verify).

3. **Pilot tenant** (e.g. `primewise`): [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md) — includes `seed_pages` + page permissions (required for V2 UI).

4. **V2 web UI after restore** (Role Centre, domains, Origin login, nginx JWT, subscription): [11-restore-to-v2-ui-checklist.md](./11-restore-to-v2-ui-checklist.md) — **required** whenever you restore into another DB and expect the frontend to work.

5. Complete data todos (01, ledger cleanup) + remaining tenants the same way as 08 + 11.

6. **New company signup speed:** rebuild pre-seeded template per [09-preseeded-zentro-template.md](./09-preseeded-zentro-template.md).

7. Smoke test per tenant (payments, posting, permissions, admin login, Role Centre).



---



## Other production docs (outside this folder)



| Doc | Purpose |

|-----|---------|

| [../PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md) | Migrations, seeds, verification |

| [../PRODUCTION_SETUP_COMMANDS.txt](../PRODUCTION_SETUP_COMMANDS.txt) | General deployment commands |

| [../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md](../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md) | Schema drift after restore |

| [../docs/branch_dimension_backfill_production.md](../docs/branch_dimension_backfill_production.md) | Branch / dimension backfill |

| [../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md](../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md) | `_zentro_template` after migrations |

| [../docs/template-schema.md](../docs/template-schema.md) | Pre-seeded golden template (signup clone) |

| [../docs/COMPANY_CREATION_PERFORMANCE.md](../docs/COMPANY_CREATION_PERFORMANCE.md) | Signup timing / baseline skip |

| [../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md) | `token_valid_after` repair |


