# 📚 ZentroApp Backend Documentation

Welcome to the ZentroApp Backend documentation! All documentation is organized by feature/system.

---

## 📂 Documentation Structure

---

### 🚀 [ZentroApp → V2 migration todos](../zentroapp-to-v2-todos/README.md)

Post-restore checklists when moving production to **zentroapp-webV2** (single folder under `backend/`).

- [README.md](../zentroapp-to-v2-todos/README.md) — todo index
- [01-payment-ledger-applies-to-id.md](../zentroapp-to-v2-todos/01-payment-ledger-applies-to-id.md) — payment cleanup (pending on prod)

---

### 🔄 [Reversal System](./reversal-system/README.md)

Complete sales invoice reversal system with credit memos, ledger tracking, and audit trails.

**Key Documents:**

- [README.md](./reversal-system/README.md) - Main overview
- [QUICK_START_REVERSAL.md](./reversal-system/QUICK_START_REVERSAL.md) - Quick start guide
- [REVERSAL_FINAL_SUMMARY.md](./reversal-system/REVERSAL_FINAL_SUMMARY.md) - Latest implementation summary
- [SALES_REVERSAL_IMPLEMENTATION.md](./reversal-system/SALES_REVERSAL_IMPLEMENTATION.md) - Original plan

**What It Does:**

- Preview reversal before execution
- Reverse Invoice + Payment entries
- Create credit memos automatically
- Bidirectional linking (Original ↔ Reversal)
- Complete audit trail

---

### 🧩 [Module System](./module-system/MODULE_SYSTEM_GUIDE.md)

Subscription-based module gating system that controls which features each company can access.

**Key Documents:**

- [MODULE_SYSTEM_GUIDE.md](./module-system/MODULE_SYSTEM_GUIDE.md) - Complete guide

**What It Does:**

- 3-layer access control: Modules (company) → Role Center (user) → Permissions (CRUD)
- 19 modules across 4 tiers: Core, Business+, Pro, Add-on
- Subscription plan → module mapping with automatic computation
- Admin waivers/deals via `module_overrides`
- Frontend navigation gating via `module` property
- Self-healing at login and API endpoints

---

### 🔐 [Permissions System](./permissions-system/README.md)

3-Layer hybrid access control system inspired by Microsoft Business Central.

**Key Documents:**

- [README.md](./permissions-system/README.md) - System overview
- [PERMISSIONS_SYSTEM_GUIDE.md](./permissions-system/PERMISSIONS_SYSTEM_GUIDE.md) - Complete guide
- [PERMISSION_SYSTEM_QUICK_GUIDE.md](./permissions-system/PERMISSION_SYSTEM_QUICK_GUIDE.md) - Quick reference
- [ROLES_AND_PERMISSIONS_EXPLAINED.md](./permissions-system/ROLES_AND_PERMISSIONS_EXPLAINED.md) - Concepts explained

**What It Does:**

- Layer 1: Role Center (Module visibility)
- Layer 2: Permission Sets (Page visibility)
- Layer 3: CRUD Permissions (Action control)
- JWT-based authorization
- Frontend route protection

---

### 🏢 [Role Center System](./role-center/README.md)

Microsoft Business Central inspired role center navigation and workspace.

**Key Documents:**

- [README.md](./role-center/README.md) - System overview
- [ROLE_CENTER_QUICK_START.md](./role-center/ROLE_CENTER_QUICK_START.md) - Quick start
- [ROLE_CENTER_VISUAL_GUIDE.md](./role-center/ROLE_CENTER_VISUAL_GUIDE.md) - Visual guide
- [ROLE_CENTER_FINAL_SUMMARY.md](./role-center/ROLE_CENTER_FINAL_SUMMARY.md) - Implementation summary

**What It Does:**

- Role-based navigation
- Module filtering
- Business Central UI/UX
- Activity tiles and quick links

---

### 💼 [Sales Pilot](./sales-pilot/README.md)

Complete sales module pilot implementation.

**Key Documents:**

- [README.md](./sales-pilot/README.md) - Overview
- [SALES_PILOT_QUICK_START.md](./sales-pilot/SALES_PILOT_QUICK_START.md) - Quick start
- [SALES_PILOT_COMPLETE_SUMMARY.md](./sales-pilot/SALES_PILOT_COMPLETE_SUMMARY.md) - Implementation summary
- [SALES_PILOT_CHECKLIST.md](./sales-pilot/SALES_PILOT_CHECKLIST.md) - Testing checklist

**What It Does:**

- Sales invoices with posting
- Customer management
- Inventory integration
- Payment processing

---

### 🏭 [Production BOM](./production-bom/)

Production Bill of Materials system for manufacturing.

**Key Documents:**

- Session auth fixes
- Unit of measure filtering
- Line number automation
- Status field updates

**What It Does:**

- Manage production BOMs
- Unit of measure conversions
- Component tracking
- Manufacturing structure

---

### 💰 [Cost Structure](./cost-structure/)

Cost calculation and structure management.

**Key Documents:**

- [COST_STRUCTURE_SUMMARY.md](./cost-structure/COST_STRUCTURE_SUMMARY.md)
- [COST_STRUCTURE_QUICK_REF.md](./cost-structure/COST_STRUCTURE_QUICK_REF.md)
- [COST_STRUCTURE_FIXES.md](./cost-structure/COST_STRUCTURE_FIXES.md)

---

### 🔧 [Resources BOM](./resources-bom/README.md)

Resource Bill of Materials for service/resource management.

**Key Documents:**

- [README.md](./resources-bom/README.md) - Overview
- [RESOURCES_BOM_TASKS.md](./resources-bom/RESOURCES_BOM_TASKS.md) - Task list
- [RESOURCES_BOM_CHECKLIST.md](./resources-bom/RESOURCES_BOM_CHECKLIST.md) - Checklist

---

### 🔄 [Admin Sync](./admin-sync/README.md)

Django admin synchronization and action utilities.

**Key Documents:**

- [README.md](./admin-sync/README.md) - Guide
- [SETUP_ADMIN_SYNC.md](./admin-sync/SETUP_ADMIN_SYNC.md) - Setup
- [ADMIN_ACTION_QUICK_START.md](./admin-sync/ADMIN_ACTION_QUICK_START.md) - Quick start

---

### 📋 [General](./general/)

General fixes, updates, and miscellaneous documentation.

**Key Documents:**

- Session fixes
- Browser compatibility
- Django tenants updates
- Field naming conventions
- API testing guides
- [SSL/TLS: nginx reload after Certbot](./general/SSL_TLS_NGINX_RELOAD_AFTER_CERTBOT_RUNBOOK.md) (wildcard backend certificate)

---

## 🎯 Quick Links

### Most Important Docs

1. **Module System** → [MODULE_SYSTEM_GUIDE.md](./module-system/MODULE_SYSTEM_GUIDE.md)
2. **Reversal System** → [REVERSAL_FINAL_SUMMARY.md](./reversal-system/REVERSAL_FINAL_SUMMARY.md)
3. **Permissions** → [PERMISSIONS_SYSTEM_GUIDE.md](./permissions-system/PERMISSIONS_SYSTEM_GUIDE.md)
4. **Role Centers** → [ROLE_CENTER_VISUAL_GUIDE.md](./role-center/ROLE_CENTER_VISUAL_GUIDE.md)

### Quick Start Guides

- [Reversal Quick Start](./reversal-system/QUICK_START_REVERSAL.md)
- [Sales Pilot Quick Start](./sales-pilot/SALES_PILOT_QUICK_START.md)
- [Role Center Quick Start](./role-center/ROLE_CENTER_QUICK_START.md)

---

## 📖 Documentation Standards

### File Naming Convention

- `README.md` - Main overview for each category
- `*_SUMMARY.md` - Implementation summaries
- `*_GUIDE.md` - Comprehensive guides
- `*_QUICK_START.md` - Quick reference guides
- `*_COMPLETE.md` - Completion reports
- `*_PLAN.md` - Planning documents

### Content Structure

Each major feature should have:

1. **README.md** - Overview and navigation
2. **QUICK_START.md** - How to use it
3. **Implementation docs** - How it was built
4. **Testing guides** - How to test it

---

## 🔍 Finding What You Need

### By Task

- **Moving production to V2?** → [zentroapp-to-v2-todos/](../zentroapp-to-v2-todos/)
- **Understanding modules & subscriptions?** → [module-system/](./module-system/)
- **Reversing invoices?** → [reversal-system/](./reversal-system/)
- **Setting up permissions?** → [permissions-system/](./permissions-system/)
- **Configuring role centers?** → [role-center/](./role-center/)
- **Working with sales?** → [sales-pilot/](./sales-pilot/)

### By Document Type

- **Quick Starts** - Look for `*_QUICK_START.md` files
- **Complete Guides** - Look for `*_GUIDE.md` or `README.md` files
- **Implementation History** - Look for `*_COMPLETE.md` files
- **Planning Docs** - Look for `*_PLAN.md` files

---

## 📊 Documentation Stats

- **Total Categories:** 9
- **Total Documents:** 90+
- **Systems Documented:** 8 major features
- **Quick Start Guides:** 10+
- **Comprehensive Guides:** 15+

---

**Last Updated:** October 30, 2024  
**Maintained by:** Development Team  
**Status:** Active & Up-to-date ✅
