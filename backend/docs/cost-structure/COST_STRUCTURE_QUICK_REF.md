# 💡 Resource Cost Structure - Quick Reference

## 📐 **The Formula**

```
Unit Cost = Direct Unit Cost + (Direct Unit Cost × Indirect Cost % ÷ 100)

OR

Unit Cost = Direct Unit Cost × (1 + Indirect Cost % ÷ 100)
```

---

## 🎯 **Real-World Examples**

### **Example 1: Basic Calculation**
```
Direct Unit Cost: 10,000 UGX
Indirect Cost %:  10%

Calculation:
Indirect Amount = 10,000 × 0.10 = 1,000
Unit Cost = 10,000 + 1,000 = 11,000 UGX
```

### **Example 2: High Overhead Business**
```
Direct Unit Cost: 20,000 UGX
Indirect Cost %:  25%

Calculation:
Indirect Amount = 20,000 × 0.25 = 5,000
Unit Cost = 20,000 + 5,000 = 25,000 UGX
```

### **Example 3: Low Overhead (Home-Based)**
```
Direct Unit Cost: 15,000 UGX
Indirect Cost %:  5%

Calculation:
Indirect Amount = 15,000 × 0.05 = 750
Unit Cost = 15,000 + 750 = 15,750 UGX
```

---

## 📊 **Complete Example: Master Stylist**

| Field | Value | Notes |
|-------|-------|-------|
| **Base Unit** | Hour | Billing unit |
| **Direct Unit Cost** | 25,000 | Stylist's hourly wage |
| **Indirect Cost %** | 10% | Salon overhead |
| **Indirect Cost Amount** | 2,500 | 25,000 × 10% |
| **Unit Cost** | **27,500** | Total cost (auto) |
| **Unit Price** | 80,000 | Customer rate |
| **Profit Per Unit** | 52,500 | Price - Cost |
| **Profit Margin** | 65.63% | Profit ÷ Price |

---

## 🔑 **Key Points**

1. ✅ **Direct Unit Cost** = What you pay the resource (wage, fuel, etc.)
2. ✅ **Indirect Cost %** = Your overhead (rent, admin, utilities)
3. ✅ **Unit Cost** = Auto-calculated (read-only)
4. ✅ **Unit Price** = What customer pays
5. ✅ **Profit** = Unit Price - Unit Cost

---

## ⚠️ **Common Mistakes**

### ❌ **Mistake 1: Setting Unit Cost Manually**
```
Unit Cost is AUTO-CALCULATED! Don't try to set it.
Set Direct Unit Cost and Indirect Cost % instead.
```

### ❌ **Mistake 2: Wrong Overhead %**
```
Too Low:  2% (unrealistic for most businesses)
Too High: 150% (exceeds 100% validation limit)
Typical:  10-25% for service businesses
```

### ❌ **Mistake 3: Including Overhead in Direct Cost**
```
Direct Cost should NOT include rent, utilities, admin.
Only include costs directly tied to the job.
```

---

## 📱 **API Usage**

### **Creating a Resource:**

```json
POST /api/resources/

{
  "name": "Jane Doe - Master Stylist",
  "resourceType": "person",
  "baseUnit": "HOUR",
  "directUnitCost": 25000,    // ← Input
  "indirectCostPct": 10,      // ← Input
  "unitPrice": 80000          // ← Input
}

// unitCost is calculated automatically!
```

### **Response:**

```json
{
  "id": 1,
  "code": "RES-TMP-1234",
  "name": "Jane Doe - Master Stylist",
  "directUnitCost": 25000.00,
  "indirectCostPct": 10.00,
  "indirectCostAmount": 2500.00,  // ← Calculated
  "unitCost": 27500.00,           // ← Auto-calculated
  "unitPrice": 80000.00,
  "profitPerUnit": 52500.00,
  "profitMargin": 65.63
}
```

---

## 🧮 **Quick Calculation Table**

| Direct Cost | Overhead % | Indirect Amount | Unit Cost |
|-------------|------------|-----------------|-----------|
| 10,000 | 5% | 500 | 10,500 |
| 10,000 | 10% | 1,000 | 11,000 |
| 10,000 | 15% | 1,500 | 11,500 |
| 10,000 | 20% | 2,000 | 12,000 |
| 10,000 | 25% | 2,500 | 12,500 |
| 20,000 | 10% | 2,000 | 22,000 |
| 20,000 | 15% | 3,000 | 23,000 |
| 20,000 | 20% | 4,000 | 24,000 |
| 50,000 | 10% | 5,000 | 55,000 |
| 50,000 | 15% | 7,500 | 57,500 |

---

## 🎯 **Industry Benchmarks**

### **Typical Indirect Cost % by Business Type:**

| Business Type | Typical Overhead |
|---------------|------------------|
| **Home-based Services** | 5-10% |
| **Small Salon/Spa** | 10-15% |
| **Medium Business** | 15-20% |
| **High-end Facility** | 20-30% |
| **Large Restaurant** | 25-35% |

---

## ✅ **Validation Rules**

```
✓ Direct Unit Cost >= 0
✓ Indirect Cost % >= 0
✓ Indirect Cost % <= 100
✓ Unit Price >= 0
✓ Unit Price >= Calculated Unit Cost
```

---

## 🔄 **What Happens When You Save?**

```
1. You enter: Direct Unit Cost = 10,000
2. You enter: Indirect Cost % = 10
3. System calculates: Unit Cost = 11,000
4. System validates: Unit Price >= 11,000
5. If valid: Resource saved ✅
6. If invalid: Error message ❌
```

---

## 📞 **Support**

Need help with cost calculations?
- Check the full documentation: `COST_STRUCTURE_UPDATE.md`
- Test in Django Admin: `/admin/resources/resource/`
- API Endpoint: `/api/resources/`

**Remember:** Unit Cost is ALWAYS auto-calculated! 🎉



