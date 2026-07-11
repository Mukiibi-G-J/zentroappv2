# G/L 2110 vs ValueEntry variance — investigation guide

## Run the diagnostic (read-only)

From `zentro-backend`, use the same **branch**, **start_date**, and **end_date** as the Inventory Value Movement report:

```bash
python manage.py tenant_command diagnose_inventory_gl_ve_variance \
  --schema=<your_tenant_schema> \
  --branch-code=<BRANCH_CODE> \
  --start=2026-01-01 \
  --end=2026-05-20
```

Command: [`diagnose_inventory_gl_ve_variance.py`](../management/commands/diagnose_inventory_gl_ve_variance.py)

---

### Opening-only variance (e.g. UGX 2,200, period in/out match)

When **opening** and **closing** variance are equal and **period stock in/out** show `—`:

1. The gap is **not from this period** — it existed on the day before `start_date`.
2. Run section **6) Opening variance audit** in the command output.
3. Typical causes:
   - **G/L 2110 posted without ValueEntry** (manual G/L, partial posting, import).
   - **Branch filter**: G/L includes untagged or dimension-set lines; ValueEntry filtered by `global_dimension_1` only.
   - **Document tie-out**: same `document_no` on G/L and VE but different amounts before period start.

Fix: backfill missing ValueEntry / branch on old docs, or post correcting adjustment — not the current period COGS (already matches).

---

| Metric | G/L | ValueEntry | Variance (G/L − VE) |
|--------|-----|------------|---------------------|
| Opening | 13,175,073.00 | 13,175,073.00 | 0 |
| Period stock in | 3,113,272.60 | 4,353,108.60 | **−1,239,836.00** |
| Period stock out | 4,464,331.00 | 3,224,495.00 | **+1,239,836.00** |
| Closing | 11,824,014.60 | 14,303,686.60 | **−2,479,672.00** |

**Checks:**

1. **Symmetric period variance:** −1,239,836 + 1,239,836 = 0 → one amount is on opposite “sides” between G/L and VE.
2. **Closing variance = 2 × swing:** Period net G/L = −1,351,058.40; period net VE = +1,128,613.60; difference = **−2,479,672** = 2 × 1,239,836 (because opening already matches).
3. **G/L breakdown sums to totals:** Purchase 1,133,175.60 + Positive Adjustment 1,980,097.00 = 3,113,272.60; COGS 3,224,495.00 + Negative Adjustment 1,239,836.00 = 4,464,331.00.
4. **That 1,239,836** is exactly **Negative Adjustment on G/L** (118 lines) — the prime suspect for misclassification on ValueEntry.

---

## Root causes

### 1. Different rules for period totals (primary for your screenshot)

| Source | Period stock in | Period stock out |
|--------|-----------------|------------------|
| **G/L 2110** | Sum of positive `amount` | Sum of abs(negative `amount`) |
| **ValueEntry (comparison column)** | Sum of `cost_amount` where **`item_ledger_entry_quantity > 0`** | Sum where **qty < 0** |

**G/L** classifies negative adjustments by **posting** (credit to inventory = stock out).

**ValueEntry** comparison totals use **quantity sign**, not entry type. If negative-adjustment rows have **positive quantity** in the database, the report counts **~1,239,836 as stock in** instead of stock out — matching your inbound/outbound variances.

Expected posting when journals use [`items/admin.py`](../../items/admin.py) `_create_value_entries()` (lines 846–849):

```python
base_fields["item_ledger_entry_quantity"] = -quantity
base_fields["cost_amount"] = -total
```

Wrong signs can come from older data, imports ([`items/tasks.py`](../../items/tasks.py)), or purchase/credit paths.

### 2. VE sub-rows vs VE column totals (display)

Sub-rows in the comparison table use **entry-type category** (`Negative Adjustment` → Stock Out). Column totals still use **qty > 0 / qty < 0**. So VE can show:

- Column stock out: **3,224,495**
- Sub-rows: COGS **4,357,670** + Negative Adjustment **1,239,836** (do not sum to the column)

That is a **report consistency** issue, not necessarily missing G/L.

### 3. Opening match ≠ ongoing agreement

Opening can match while period rules diverge. Closing drift = period net difference when opening variance is zero.

### 4. Branch / scope

G/L may use company-wide 2110 when branch lines are untagged; ValueEntry filters `global_dimension_1` only. Unlikely if opening matches exactly for the same branch filter.

---

## Investigation checklist (on your tenant)

1. Run `diagnose_inventory_gl_ve_variance` with report filters.
2. Section **2**: if `qty > 0` sum on negative adjustments ≈ **1,239,836** → **confirmed**.
3. Section **3**: sample `document_no` — compare VE qty/cost vs G/L amount on 2110.
4. Section **4**: Purchase G/L vs VE `Purchase` entry type by `document_no`.

---

## Recommended fix scope (after confirmation)

| Priority | Action | Scope |
|----------|--------|--------|
| **1** | Fix ValueEntry rows with positive qty (or wrong cost sign) on negative adjustments | Data + repost affected journals |
| **2** | Harden all posting/import paths to always negate qty/cost for negative adjustments | Posting code |
| **3** | Align VE **period totals** in reconciliation with `ENTRY_TYPE_CATEGORY` (same as sub-rows) | Report-only; books unchanged |
| **4** | Optional: fix SQL `Cast(cost_amount)` when `cost_amount` is empty string | Report service robustness |

**Do not** treat ValueEntry column totals as the legal inventory balance when headline figures are G/L 2110 — use G/L for management; use VE for item-level trace after aligning rules.

---

## Local dev note

The attached screenshot totals were not reproduced on the local company list (no tenant with opening ≈ 13,175,073 in a full scan). Run the command on **production/staging** with the tenant and branch used in the UI.

---

## Fixes implemented

1. **Posting** — `items/admin.py` (`_create_value_entries`, `_preview_value_entries`) and `items/posting.py`: use `abs()` before negative signs so item ledger rows already negative are not flipped positive.
2. **Report** — `inventory_value_movement_service.py`: ValueEntry comparison totals use `ENTRY_TYPE_CATEGORY` (aligned with breakdown); safe `cost_amount` parsing (no SQL cast on empty strings).
3. **Data repair** — `python manage.py tenant_command repair_negative_adjustment_value_entries --schema=<tenant> --dry-run` then `--apply`.

Refresh the report after deploy (cache **v13**). Run repair on production tenants with historical mis-signed rows.
