# 📋 General Documentation

General fixes, updates, and miscellaneous documentation for the ZentroApp backend.

---

## 📂 Contents

### Session & Authentication

- [SESSION_FIXES_SUMMARY.md](./SESSION_FIXES_SUMMARY.md) - Session-related fixes
- [SESSION_SUMMARY.md](./SESSION_SUMMARY.md) - Session management summary

### Browser Compatibility

- [BRAVE_BROWSER_FIX.md](./BRAVE_BROWSER_FIX.md) - Brave browser compatibility fixes

### Database & Models

- [DJANGO_TENANTS_UPDATE.md](./DJANGO_TENANTS_UPDATE.md) - Django tenants updates
- [DJANGO_TENANTS_FIX.md](./DJANGO_TENANTS_FIX.md) - Tenant-related fixes
- [FIELD_NAMING_UPDATE.md](./FIELD_NAMING_UPDATE.md) - Field naming conventions

### Testing & API

- [API_TEST_GUIDE.md](./API_TEST_GUIDE.md) - API testing guide
- [QUICK_START_TESTING.md](./QUICK_START_TESTING.md) - Quick testing guide

### Production / TLS (nginx + Certbot)

- [SSL_TLS_NGINX_RELOAD_AFTER_CERTBOT_RUNBOOK.md](./SSL_TLS_NGINX_RELOAD_AFTER_CERTBOT_RUNBOOK.md) - Wildcard backend cert: stale nginx TLS after renewal, reload fix, deploy hook  
  (First-time wildcard setup with Cloudflare DNS-01: repo root [`hosting.md`](../../../hosting.md).)
- [MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md](./MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md) - Login 500: missing `must_change_password` on tenant `authentication_customuser` (fake `0019` if needed, then migrate `0020`–`0026`)
- [THESTORMSCAFE_V2_SEED_RUNBOOK.md](./THESTORMSCAFE_V2_SEED_RUNBOOK.md) - Seed pages/permissions/menu for restored tenant UI (`thestormscafe` / V2 Role Centre)
- [TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](./TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md) - Auth column drift for `token_valid_after`
- [MIGRATION_STATE_DRIFT_RUNBOOK.md](./MIGRATION_STATE_DRIFT_RUNBOOK.md) - General django-tenants migration history vs schema drift

### Module Setup

- [HOTEL_MODULE_SETUP.md](./HOTEL_MODULE_SETUP.md) - Hotel management module setup

### Project Status

- [STATUS.md](./STATUS.md) - Project status
- [PROGRESS_UPDATE.md](./PROGRESS_UPDATE.md) - Progress updates
- [COMPLETE_SUMMARY.md](./COMPLETE_SUMMARY.md) - Completion summaries
- [IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md) - Implementation reports
- [FINAL_SUMMARY.md](./FINAL_SUMMARY.md) - Final summaries

---

## 🎯 Purpose

This folder contains documentation that doesn't fit into specific feature categories but is important for:

- Bug fixes and troubleshooting
- General setup and configuration
- Cross-cutting concerns
- Development utilities
- Project status tracking

---

**Category:** General  
**Status:** Active
