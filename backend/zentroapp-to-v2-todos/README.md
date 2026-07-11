# ZentroApp → ZentroApp V2 — migration todos



**Single folder** for post-restore work when moving production from **zentroapp-web** to **zentroapp-webV2**.



Tick items per environment: **staging first**, then **production**.



---



## Start here (every prod DB restore)



**[00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)** — full replay checklist and copy-paste commands. Run this **every time** you restore a dump from production into local/dev (or before go-live).



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



Add new todos as `08-….md` in **this folder** and link them in the table above.



---



## Standard order (every environment)



1. **Backup** production database (verify restore path).

2. **Follow** [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md) (migrate → sequences → repairs → verify).

3. Complete data todos (01, seeds, permissions) per [../PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md).

4. Smoke test per tenant (payments, posting, permissions, admin login).



---



## Other production docs (outside this folder)



| Doc | Purpose |

|-----|---------|

| [../PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md) | Migrations, seeds, verification |

| [../PRODUCTION_SETUP_COMMANDS.txt](../PRODUCTION_SETUP_COMMANDS.txt) | General deployment commands |

| [../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md](../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md) | Schema drift after restore |

| [../docs/branch_dimension_backfill_production.md](../docs/branch_dimension_backfill_production.md) | Branch / dimension backfill |

| [../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md](../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md) | `_zentro_template` after migrations |

| [../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md) | `token_valid_after` repair |


