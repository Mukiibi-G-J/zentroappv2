# 🧪 Resources & BOM API Testing Guide

## 🎯 Quick API Tests (Using Django Admin for Token)

### Step 1: Get Authentication Token

1. Login to Django admin: http://localhost:8000/admin/
2. Or use existing JWT token from frontend

### Step 2: Test Resources API

#### List Resources

```bash
GET http://localhost:8000/api/resources/
```

#### Create Resource

```bash
POST http://localhost:8000/api/resources/create/
Content-Type: application/json

{
  "name": "Jane Doe - Master Stylist",
  "resourceType": "person",
  "baseUnit": "HOUR",
  "costRate": 25000,
  "chargeRate": 80000,
  "description": "Master stylist with 10 years experience",
  "isActive": true
}
```

#### Get Available Resources (for POS)

```bash
GET http://localhost:8000/api/resources/available/?resourceType=person
```

---

### Step 3: Test Production BOM API

#### List BOMs

```bash
GET http://localhost:8000/api/production/boms/
```

#### Create BOM with Lines

```bash
POST http://localhost:8000/api/production/boms/create/
Content-Type: application/json

{
  "name": "Men's Haircut Recipe",
  "serviceItem": [SERVICE_ITEM_ID],
  "notes": "Standard men's haircut procedure",
  "lines": [
    {
      "lineNumber": 1,
      "lineType": "resource",
      "resource": [RESOURCE_ID],
      "resourceQuantity": 0.5,
      "notes": "30 minutes of stylist time"
    },
    {
      "lineNumber": 2,
      "lineType": "inventory",
      "inventoryItem": "[INVENTORY_ITEM_NO]",
      "inventoryQuantity": 1,
      "notes": "Shampoo"
    }
  ]
}
```

#### Get BOM Cost Analysis

```bash
GET http://localhost:8000/api/production/boms/[BOM_ID]/cost-analysis/
```

---

### Step 4: Test Service Sales API

#### Process Service Sale

```bash
POST http://localhost:8000/api/sales/process-service-sale/
Content-Type: application/json

{
  "saleLineId": [SALE_LINE_ID]
}
```

#### Get Service Profitability

```bash
GET http://localhost:8000/api/sales/service-profitability/?startDate=2025-01-01&endDate=2025-12-31
```

#### Get Service Cost Breakdown

```bash
GET http://localhost:8000/api/sales/service-cost-breakdown/[SERVICE_ITEM_NO]/
```

---

## ✅ Expected Responses

### Resources List Response:

```json
{
  "count": 10,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 1,
      "code": "RES-TMP-1234",
      "name": "Jane Doe - Master Stylist",
      "resourceType": "person",
      "baseUnit": "HOUR",
      "costRate": "25000.00",
      "chargeRate": "80000.00",
      "isActive": true,
      "profitPerUnit": 55000.0,
      "profitMargin": 68.75
    }
  ]
}
```

### BOM Detail Response:

```json
{
  "id": 1,
  "bomCode": "BOM-TMP-5678",
  "name": "Men's Haircut Recipe",
  "serviceItem": {
    "id": "SVC-001",
    "name": "Men's Precision Haircut",
    "unitPrice": 60000
  },
  "lines": [
    {
      "id": 1,
      "lineNumber": 1,
      "lineType": "resource",
      "resourceData": {
        "name": "Jane Doe - Master Stylist",
        "costRate": 25000.0
      },
      "resourceQuantity": "0.500",
      "unitCost": "25000.00",
      "totalCost": "12500.00"
    }
  ],
  "totalCost": 16000.0,
  "profitMargin": 73.33,
  "lineCount": 2
}
```

### Service Profitability Response:

```json
{
  "summary": {
    "totalSales": 50,
    "totalRevenue": 3000000,
    "totalCost": 800000,
    "totalProfit": 2200000,
    "avgProfitMargin": 73.33
  },
  "topServices": [
    {
      "itemId": "SVC-001",
      "serviceName": "Men's Precision Haircut",
      "salesCount": 25,
      "totalRevenue": 1500000,
      "totalCost": 400000,
      "totalProfit": 1100000,
      "profitMargin": 73.33
    }
  ]
}
```

---

## 🔧 Server Status

**Check server is running:**

- Server should be at: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/

**If server errors:**

1. Check terminal for error messages
2. Verify all migrations are applied
3. Check imports in URLs files

---

## ✅ All Endpoints

### Resources (6):

1. `GET /api/resources/` - List
2. `POST /api/resources/create/` - Create
3. `GET /api/resources/<id>/` - Get
4. `PUT /api/resources/<id>/update/` - Update
5. `DELETE /api/resources/<id>/delete/` - Delete
6. `GET /api/resources/available/` - Available

### Production BOM (9):

1. `GET /api/production/boms/` - List
2. `POST /api/production/boms/create/` - Create
3. `GET /api/production/boms/<id>/` - Get
4. `PUT /api/production/boms/<id>/update/` - Update
5. `DELETE /api/production/boms/<id>/delete/` - Delete
6. `GET /api/production/boms/<id>/cost-analysis/` - Cost Analysis
7. `POST /api/production/boms/<id>/lines/create/` - Create Line
8. `PUT /api/production/bom-lines/<id>/update/` - Update Line
9. `DELETE /api/production/bom-lines/<id>/delete/` - Delete Line

### Sales Integration (3):

1. `POST /api/sales/process-service-sale/` - Process Service Sale
2. `GET /api/sales/service-profitability/` - Profitability Report
3. `GET /api/sales/service-cost-breakdown/<id>/` - Cost Breakdown

**Total: 18 endpoints** ✅


