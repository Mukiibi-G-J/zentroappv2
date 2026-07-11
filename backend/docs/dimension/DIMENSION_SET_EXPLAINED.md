# Dimension Set ID - Visual Guide for Shoe Cleaning Business

> **Visual diagram:** See `assets/dimension-set-explained.png` for a flow diagram.

## Your Client's Need

- **2 Branches** (e.g., Branch A, Branch B)  
- **Multiple shoe types** (Sneakers, Office Shoes, Boots, Bags, etc.)  
- **Question:** *"Which shoe types generate the most income?"* (by branch, overall, etc.)

---

## 1. The Building Blocks: Dimensions

Think of **dimensions** as categories you use to slice your business data.

```
┌─────────────────────────────────────────────────────────────────────┐
│  DIMENSION 1: BRANCH                                                 │
│  (Global Dimension 1 - usually location/branch)                      │
│                                                                      │
│    ● Branch A      ● Branch B                                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  DIMENSION 2: SHOE TYPE (Item Category)                              │
│  (Global Dimension 2 - product/service category)                     │
│                                                                      │
│    ● Sneakers    ● Office Shoes    ● Boots    ● Bags    ● Leather    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. What is a Dimension Set?

A **Dimension Set** is a **single ID** that represents a **unique combination** of dimension values.

Instead of storing many columns on every sale (branch_id, shoe_type_id, ...), you store one `dimension_set_id`.

```
                    DIMENSION SET = One ID for one combination

    Branch A  +  Sneakers     →   Dimension Set #101
    Branch A  +  Office Shoes →   Dimension Set #102
    Branch A  +  Boots        →   Dimension Set #103
    Branch B  +  Sneakers     →   Dimension Set #104
    Branch B  +  Office Shoes →   Dimension Set #105
    ... and so on
```

---

## 3. Visual Flow: From Sale to Report

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER DROPS OFF SNEAKERS AT BRANCH A FOR CLEANING                         │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  YOU CREATE A SALE / INVOICE LINE                                              │
│                                                                               │
│  SalesInvoiceLine                                                             │
│  ├── item: "Basic Cleaning"                                                    │
│  ├── amount: 8,000                                                            │
│  └── dimension_set_id: 101  ◄── ONE reference to the combination below        │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  DIMENSION SET #101 (lookup table)                                            │
│                                                                               │
│  Contains:                                                                    │
│    • Branch:      Branch A                                                    │
│    • Shoe Type:   Sneakers                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. How Reports Work: "Which shoe types make the most money?"

```
                    YOUR DATA (simplified view)
                    
Sale #1:  Branch A + Sneakers      → 8,000     (dimension_set 101)
Sale #2:  Branch A + Sneakers      → 8,000     (dimension_set 101)
Sale #3:  Branch A + Office Shoes → 12,000    (dimension_set 102)
Sale #4:  Branch B + Sneakers      → 8,000     (dimension_set 104)
Sale #5:  Branch B + Boots        → 15,000    (dimension_set 106)
...
```

**Report: Total income by Shoe Type (all branches)**

```
Join: Sales Lines → Dimension Set → Dimension Values (where dimension = "Shoe Type")

    Sneakers:      8,000 + 8,000 + 8,000 = 24,000
    Office Shoes:  12,000
    Boots:         15,000
```

**Report: Income by Branch AND Shoe Type**

```
    Branch A + Sneakers:      16,000
    Branch A + Office Shoes:  12,000
    Branch B + Sneakers:      8,000
    Branch B + Boots:         15,000
```

---

## 5. Why Not Just Store Branch + Shoe Type Directly?

You *could* have `global_dimension_1_id` (branch) and `global_dimension_2_id` (shoe type) on every line. ZentroApp supports both:

| Approach | Use Case |
|----------|----------|
| **global_dimension_1 + global_dimension_2** | Quick, simple – exactly 2 dimensions. Works when G/L Setup defines "Dim 1 = Branch, Dim 2 = Shoe Type". |
| **dimension_set_id only** | Flexible – can add more dimensions later (e.g. Service Type, Promo Code) without new columns. |

For your client (2 dimensions: Branch + Shoe Type), both work. **Dimension Set** becomes useful when you want more dimensions or cleaner reporting.

---

## 6. Setup Checklist for Shoe Cleaning Client

1. **Create Dimension Values:**
   - Dimension "BRANCH": Branch A, Branch B  
   - Dimension "SHOE_TYPE": Sneakers, Office Shoes, Boots, Bags, Leather  

2. **Link in G/L Setup:**
   - Global Dimension 1 → BRANCH  
   - Global Dimension 2 → SHOE_TYPE  

3. **On each sale/invoice line:**
   - Assign the correct dimension set (or global_dimension_1 + global_dimension_2) based on branch and shoe type.  

4. **Reports:**
   - Use dimension_set (or global_dimension_1/2) to group and sum by Branch, Shoe Type, or both.

---

## 7. Quick Reference Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRANSACTION (Sale)                            │
│                                                                  │
│   Amount: 8,000    dimension_set_id: 101                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │  points to
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DIMENSION SET #101                              │
│                                                                  │
│   ┌─────────────┬──────────────┐                                 │
│   │ Dimension   │ Value        │                                 │
│   ├─────────────┼──────────────┤                                 │
│   │ Branch      │ Branch A     │                                 │
│   │ Shoe Type   │ Sneakers     │                                 │
│   └─────────────┴──────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │  enables
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  REPORTS: "Sneakers made 24K", "Branch A made 28K", etc.        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Default Dimension (Business Central Concept)

**Default Dimension** = a dimension value that is **automatically suggested** when you create a document or line for a specific entity (Customer, Item, Location, etc.).

### How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEFAULT DIMENSION = "When I see X, pre-fill dimension with Y"       │
│                                                                      │
│  Example rules:                                                       │
│    • For Customer "ABC Ltd"     → Branch = Branch A                  │
│    • For Item "Basic Cleaning"  → Shoe Type = Sneakers               │
│    • For Location "Ntinda"      → Branch = Branch A                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Shoe Cleaning Example

| Entity      | Entity No/Code | Dimension   | Default Value | Effect                                                            |
|-------------|----------------|------------|---------------|-------------------------------------------------------------------|
| Customer    | CUST-001       | Branch     | Branch A      | Sales to CUST-001 auto-fill Branch = Branch A                    |
| Item        | SNEAKERS       | Shoe Type  | Sneakers      | When adding "Sneakers" service to a line, Shoe Type = Sneakers   |
| Item        | OFFICE-SHOES   | Shoe Type  | Office Shoes  | When adding office shoe cleaning, Shoe Type = Office Shoes       |
| Location    | NTINDA         | Branch     | Branch A      | Lines at Ntinda location get Branch = Branch A                   |

### Value Posting (BC Rules)

| Value       | Meaning                                                                 |
|-------------|-------------------------------------------------------------------------|
| **None**    | Default is suggested but can be overridden on the line                  |
| **Code Mandatory** | User must enter a value; default is not enough                         |
| **Same Code**      | Once set, all lines must use the same dimension value (stricter)        |

### Flow: Sale with Default Dimensions

```
1. User creates Sales Order for Customer "ABC Ltd"
2. System looks up DefaultDimension: Customer ABC Ltd → Branch = Branch A
3. Invoice line gets dimension_set with Branch A (pre-filled)
4. User adds Item "Basic Cleaning" (Sneakers)
5. System looks up DefaultDimension: Item Basic Cleaning → Shoe Type = Sneakers
6. Line merges: Branch A + Sneakers → dimension_set #101
7. User can override if Value Posting = None
```

### In ZentroApp

- **Model:** `dimension.DefaultDimension`
- **Fields:** `table` (which entity type), `no` (entity id/code), `dimension_code`, `dimension_value`, `value_posting`
- **Used by:** Resources, and can be extended to Customers, Items, Locations, etc.
- **Admin:** Setup → Dimension → Default Dimensions

---

## Summary

- **Dimension** = category (Branch, Shoe Type).  
- **Dimension Value** = option in that category (Branch A, Sneakers).  
- **Dimension Set** = one ID for a unique combination (Branch A + Sneakers).  
- **Default Dimension** = rule that pre-fills dimensions (e.g. Customer X → Branch A, Item Y → Shoe Type Sneakers).  
- **On each sale** you store the dimension_set_id (or global_dimension_1 + global_dimension_2).  
- **Reports** join through that to show income by branch, shoe type, or both.
