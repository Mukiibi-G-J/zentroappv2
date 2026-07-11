# ✅ Pagination Dropdown Implementation Guide

## 🎯 **Overview**

This guide explains how to implement a working pagination dropdown (page size selector) that allows users to choose how many items to display per page (10, 25, 50, 100). This was implemented for the Items page and can be applied to any other page using `BaseTable`.

---

## 📋 **Problem Statement**

**Before:** The pagination dropdown in `BaseTable` didn't work. When users selected a different page size (e.g., 25 items per page), nothing happened because:
1. The `BaseTable` component didn't have a handler for page size changes
2. The `DataTable` component was slicing data on the client-side even though the backend already paginated
3. The backend ViewSet didn't accept the `page_size` parameter
4. Frontend was sending `pageSize` (camelCase) but backend expected `page_size` (snake_case)

**After:** Users can now select any page size (10, 25, 50, 100) and see that many items on the first page, with pagination controls correctly showing the total number of pages.

---

## 🔧 **Implementation Steps**

### **Step 1: Update BaseTable Component**

**File:** `zentro-frontend/src/views/components/shared/TableSystem/components/BaseTable.tsx`

#### 1.1 Add `onPageSizeChange` to the interface:

```typescript
export interface BaseTableProps<T, F = FilterQueries> {
  // ... existing props ...
  onPaginationChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void; // ✅ ADD THIS
  onSort: (sort: { key: string; order: "asc" | "desc" }) => void;
  // ... rest of props ...
}
```

#### 1.2 Add `onPageSizeChange` to component parameters:

```typescript
export const BaseTable = <T extends Record<string, any>, F = FilterQueries>({
  // ... existing params ...
  onPaginationChange,
  onPageSizeChange, // ✅ ADD THIS
  onSort,
  // ... rest of params ...
}: BaseTableProps<T, F>) => {
```

#### 1.3 Pass `onPageSizeChange` to DataTable:

```typescript
<DataTable
  columns={columns}
  data={data}
  loading={loading}
  pagingData={{
    total: Number(tableData.total) || 0,
    pageIndex: Number(tableData.pageIndex) || 1,
    pageSize: Number(tableData.pageSize) || 10,
  }}
  onPaginationChange={onPaginationChange}
  onSelectChange={(pageSize) => { // ✅ ADD THIS
    if (onPageSizeChange) {
      onPageSizeChange(Number(pageSize));
    }
  }}
  onSort={(sortParam: OnSortParam) => {
    onSort({
      key: String(sortParam.key),
      order: sortParam.order as "asc" | "desc",
    });
  }}
/>
```

---

### **Step 2: Remove Client-Side Data Slicing**

**File:** `zentro-frontend/src/components/shared/DataTable.tsx`

**Before:**
```typescript
{table
  .getRowModel()
  .rows.slice(0, pageSize) // ❌ REMOVE THIS
  .map((row) => {
```

**After:**
```typescript
{table
  .getRowModel()
  .rows // ✅ Backend already paginates, no need to slice
  .map((row) => {
```

**Why:** The backend already returns only the items for the current page. Slicing again on the client would limit the display incorrectly.

---

### **Step 3: Add Page Size Change Handler in Your Page Component**

**File:** `zentro-frontend/src/views/items/Items.tsx` (or your page component)

Add the `onPageSizeChange` handler to your `BaseTable`:

```typescript
<BaseTable<Item, FilterQueries>
  title="Items"
  columns={columns}
  data={data}
  loading={loading}
  tableData={tableData}
  onPaginationChange={(page: number) => {
    dispatch(
      itemActions.setTableData({
        ...tableDataRef.current,
        pageIndex: page,
      })
    );
  }}
  onPageSizeChange={(pageSize: number) => { // ✅ ADD THIS
    dispatch(
      itemActions.setTableData({
        ...tableDataRef.current,
        pageSize: pageSize,
        pageIndex: 1, // Reset to first page when page size changes
      })
    );
  }}
  onSort={(sortData: { key: string; order: "asc" | "desc" }) => {
    dispatch(
      itemActions.setTableData({
        ...tableDataRef.current,
        sort: sortData,
      })
    );
  }}
  // ... other props ...
/>
```

**Important:** Always reset `pageIndex` to `1` when the page size changes to avoid showing an empty page.

---

### **Step 4: Update Backend ViewSet to Accept page_size Parameter**

**File:** `zentro-backend/items/views.py` (or your app's views.py)

#### 4.1 Create or use a pagination class that accepts `page_size`:

```python
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100  # Default page size
    page_size_query_param = "page_size"  # Allows ?page_size=25
    max_page_size = 1000  # Maximum allowed page size
```

**Important:** Define this class **before** your ViewSet class.

#### 4.2 Add pagination class to your ViewSet:

```python
class ItemsModalViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    # ... other settings ...
    pagination_class = StandardResultsSetPagination  # ✅ ADD THIS
```

---

### **Step 5: Map Frontend Parameter Names to Backend**

**File:** `zentro-frontend/src/services/ItemService.ts` (or your service file)

Map `pageSize` (camelCase) to `page_size` (snake_case):

```typescript
export const apiGetItems = (params?: {
  page?: number;
  pageSize?: number; // Frontend uses camelCase
  search?: string;
  // ... other params ...
}) => {
  // Map frontend parameter names to backend parameter names
  const { search, pageSize, ...rest } = params || {};
  const backendParams = {
    ...rest,
    ...(search ? { q: search } : {}),
    ...(pageSize ? { page_size: pageSize } : {}), // ✅ Map to snake_case
  };
  return ApiService.fetchData<{
    results: Item[];
    count: number;
  }>({
    url: "/items/",
    method: "get",
    params: backendParams,
  });
};
```

---

## 📝 **Complete Example: Implementing on a New Page**

Let's say you want to implement this on a "Customers" page:

### **Frontend Changes:**

1. **Update Customers.tsx:**

```typescript
<BaseTable
  title="Customers"
  columns={columns}
  data={data}
  loading={loading}
  tableData={tableData}
  onPaginationChange={(page: number) => {
    dispatch(
      customerActions.setTableData({ ...tableData, pageIndex: page })
    );
  }}
  onPageSizeChange={(pageSize: number) => { // ✅ ADD THIS
    dispatch(
      customerActions.setTableData({
        ...tableData,
        pageSize: pageSize,
        pageIndex: 1, // Reset to first page
      })
    );
  }}
  onSort={(sortData) => {
    dispatch(customerActions.setTableData({ ...tableData, sort: sortData }));
  }}
  // ... other props ...
/>
```

2. **Update CustomerService.ts:**

```typescript
export const apiGetCustomers = (params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  // ... other params ...
}) => {
  const { search, pageSize, ...rest } = params || {};
  const backendParams = {
    ...rest,
    ...(search ? { q: search } : {}),
    ...(pageSize ? { page_size: pageSize } : {}), // ✅ Map to snake_case
  };
  return ApiService.fetchData({
    url: "/customers/",
    method: "get",
    params: backendParams,
  });
};
```

### **Backend Changes:**

1. **Update customers/views.py:**

```python
from rest_framework.pagination import PageNumberPagination

# Define pagination class BEFORE the ViewSet
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    # ... other settings ...
    pagination_class = StandardResultsSetPagination  # ✅ ADD THIS
```

---

## ✅ **Verification Checklist**

After implementing, verify:

- [ ] Selecting different page sizes (10, 25, 50, 100) updates the table
- [ ] The correct number of items appears on the first page
- [ ] Pagination controls show the correct total number of pages
- [ ] Page resets to 1 when page size changes
- [ ] Backend receives `page_size` parameter correctly
- [ ] No client-side data slicing is happening
- [ ] All items for the selected page size are displayed

---

## 🐛 **Common Issues & Solutions**

### **Issue 1: Page size changes but items don't update**

**Solution:** Make sure your `useEffect` dependency array includes `tableData.pageSize`:

```typescript
useEffect(() => {
  fetchItems();
}, [tableData.pageIndex, tableData.pageSize, tableData.query, filterData]);
// ✅ Include pageSize in dependencies
```

### **Issue 2: Backend returns wrong number of items**

**Solution:** Verify the ViewSet has `pagination_class` set and the pagination class has `page_size_query_param = "page_size"`.

### **Issue 3: Parameter name mismatch**

**Solution:** Ensure your service maps `pageSize` to `page_size`:

```typescript
...(pageSize ? { page_size: pageSize } : {})
```

### **Issue 4: Items are still being sliced on client**

**Solution:** Remove `.slice(0, pageSize)` from `DataTable.tsx` - the backend already paginates.

---

## 📚 **Files Modified (Reference)**

### **Frontend:**
- `zentro-frontend/src/views/components/shared/TableSystem/components/BaseTable.tsx`
- `zentro-frontend/src/components/shared/DataTable.tsx`
- `zentro-frontend/src/views/items/Items.tsx`
- `zentro-frontend/src/services/ItemService.ts`

### **Backend:**
- `zentro-backend/items/views.py`

---

## 🎉 **Result**

After implementing these changes:
- ✅ Users can select page size from dropdown (10, 25, 50, 100)
- ✅ Selected number of items appears on the first page
- ✅ Pagination controls correctly show total pages
- ✅ Page resets to 1 when page size changes
- ✅ Backend properly handles `page_size` parameter
- ✅ No unnecessary client-side data manipulation

---

## 📅 **Date Implemented**

December 2025

---

## 👤 **Implementation Notes**

- The pagination dropdown uses `Select` component from the UI library
- Backend uses Django REST Framework's `PageNumberPagination`
- Frontend uses Redux for state management
- All changes are backward compatible - existing pages without `onPageSizeChange` will continue to work



