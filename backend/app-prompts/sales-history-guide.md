# Sales History Implementation Guide

## Overview

This guide explains how to implement **Sales History** in the ZentroApp mobile application. This is a **high-level implementation guide** that focuses on API endpoints, data structure, filtering, and synchronization patterns for displaying and managing sales records.

## Sales History Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER OPENS SALES HISTORY SCREEN                          │
│ - Mobile: Navigate to Sales History/Reports              │
│ - Display loading indicator                              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: FETCH SALES DATA                             │
│ - Send GET request to /api/sales/                        │
│ - Apply filters (date range, customer, status)           │
│ - Request with pagination parameters                     │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS REQUEST                                 │
│ - Check READ permission (Page Object ID: 10002)          │
│ - Filter by query parameters                             │
│ - Apply pagination (default: 50 per page)                │
│ - Return sales invoices with lines                       │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: DISPLAY SALES LIST                           │
│ - Show sales cards/list items                            │
│ - Display: invoice_no, customer, date, total             │
│ - Show payment status and method                         │
│ - Enable pull-to-refresh                                 │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER APPLIES FILTERS (Optional)                          │
│ - Select date range (today, week, month, custom)         │
│ - Filter by customer                                     │
│ - Filter by status (Draft, Posted)                       │
│ - Filter by payment method                               │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER SELECTS A SALE                                      │
│ - Tap on sale item to view details                       │
│ - Navigate to Sale Detail screen                         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: FETCH SALE DETAILS                           │
│ - Send GET request to /api/sales/{id}/                   │
│ - Include lines data                                     │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: DISPLAY SALE DETAILS                         │
│ - Show header info (customer, dates, totals)             │
│ - Show all line items (item, qty, price, amount)         │
│ - Show payment information                               │
│ - Enable actions (print, share, email)                   │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Main Endpoints

#### 1. List Sales Invoices

```
GET /api/sales/
```

**Purpose:** Retrieve a paginated list of sales invoices with filtering and search capabilities.

**Authentication & Permissions:**
- **Authentication**: Required (JWT Token)
- **Permission Check**: READ permission on Page Object ID `10002` (Sales Page)
- **Permission Source**: User's permission sets via User Groups

**Query Parameters:**

```javascript
{
  // Pagination
  page: 1,                           // Page number (default: 1)
  page_size: 50,                     // Results per page (default: 50)
  
  // Search
  search: "customer name",           // Search by customer name or invoice number
  
  // Filters
  customer: 123,                     // Filter by customer ID
  status: "Posted",                  // Filter by status: "Draft" or "Posted"
  payment_method: 1,                 // Filter by payment method ID
  payment_method: "not_paid",        // Special filter for unpaid invoices
  
  // Date filters
  document_date: "2024-12-01",       // Exact date
  document_date__gte: "2024-12-01",  // From date (>=)
  document_date__lte: "2024-12-31",  // To date (<=)
  date_range_before: "2024-12-01",   // Before date
  date_range_after: "2024-12-31",    // After date
  
  posting_date__gte: "2024-12-01",   // Posted from date
  posting_date__lte: "2024-12-31",   // Posted to date
  
  // Ordering
  ordering: "-created_at"            // Order by field (prefix with - for descending)
                                     // Options: document_date, posting_date, created_at
}
```

**Response Format:**

```json
{
  "count": 150,
  "next": "http://api.zentroapp.app/api/sales/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "system_id": "uuid-string",
      "invoice_no": "SI-20241206001",
      "customer": 45,
      "customer_name": "John's Hardware Store",
      "contact_person": "John Doe",
      "document_date": "2024-12-06",
      "posting_date": "2024-12-06",
      "vat_date": "2024-12-06",
      "due_date": "2024-12-20",
      "customer_invoice_no": null,
      "total_amount": "150000.00",
      "status": "Posted",
      "amount_received": "150000.00",
      "change_amount": "0.00",
      "payment_method": 1,
      "payment_method_name": "Cash",
      "payment_method_details": {
        "id": 1,
        "code": "CASH",
        "description": "Cash"
      },
      "user": 5,
      "user_name": "Jane Cashier",
      "payment_status": "Paid",
      "created_at": "2024-12-06T10:30:00Z",
      "updated_at": "2024-12-06T10:30:00Z",
      "lines": [
        {
          "id": 456,
          "system_id": "line-uuid",
          "sales_invoice": 123,
          "item": "ITM-000001",
          "item_name": "Product A",
          "item_no": "ITM-000001",
          "quantity": "5.00",
          "unit_price": "25000.00",
          "line_discount_amount": "0.00",
          "line_amount": "125000.00",
          "total_amount": "125000.00",
          "description": "Product A",
          "unit_of_measure": "PCS",
          "location_code": "MAIN",
          "tracking_code": null,
          "uom_options": [
            {
              "code": "PCS",
              "description": "Pieces",
              "quantity_per_unit": "1.00",
              "default": true
            }
          ]
        },
        {
          "id": 457,
          "system_id": "line-uuid-2",
          "sales_invoice": 123,
          "item": "ITM-000002",
          "item_name": "Product B",
          "item_no": "ITM-000002",
          "quantity": "2.00",
          "unit_price": "12500.00",
          "line_discount_amount": "0.00",
          "line_amount": "25000.00",
          "total_amount": "25000.00",
          "description": "Product B",
          "unit_of_measure": "PCS",
          "location_code": "MAIN",
          "tracking_code": null,
          "uom_options": []
        }
      ]
    }
  ]
}
```

#### 2. Get Sales Summary/Statistics

```
GET /api/sales/summary/
```

**Purpose:** Get aggregated totals for the current filter set (useful for dashboard cards).

**Authentication & Permissions:**
- **Authentication**: Required (JWT Token)
- **Permission Check**: READ permission on Page Object ID `10004` (Sales History Page)

**Query Parameters:**
- Accepts same filters as the list endpoint

**Response Format:**

```json
{
  "total_sales": 1500000.00,      // Total amount from all filtered invoices
  "total_products": 150.00,        // Total quantity of all products sold
  "total_invoices": 45             // Count of invoices in the filtered set
}
```

#### 3. Get Single Sale Details

```
GET /api/sales/{id}/
GET /api/sales/{system_id}/
```

**Purpose:** Retrieve detailed information for a specific sale invoice.

**Authentication & Permissions:**
- **Authentication**: Required (JWT Token)
- **Permission Check**: READ permission on Page Object ID `10002`

**Path Parameters:**
- `id`: Numeric ID of the sale (e.g., `123`)
- `system_id`: UUID system ID (e.g., `uuid-string`)

**Response Format:**
Same structure as individual items in the list response, including full `lines` array.

---

## Mobile App Implementation Guide

### 1. Fetching Sales History List

**Recommended Approach:**

```javascript
// Fetch sales with filters
const fetchSalesHistory = async (filters = {}) => {
  const params = {
    page: filters.page || 1,
    page_size: 50,
    ordering: "-created_at",
    ...filters
  };
  
  // Apply date range filter if present
  if (filters.dateRange) {
    params.document_date__gte = filters.dateRange.start;
    params.document_date__lte = filters.dateRange.end;
  }
  
  // Apply customer filter
  if (filters.customer) {
    params.customer = filters.customer;
  }
  
  // Apply status filter
  if (filters.status) {
    params.status = filters.status; // "Draft" or "Posted"
  }
  
  // Apply payment method filter
  if (filters.paymentMethod) {
    params.payment_method = filters.paymentMethod;
  }
  
  try {
    const response = await api.get('/sales/', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching sales:', error);
    throw error;
  }
};
```

### 2. Implementing Date Range Filters

**Common Date Range Presets:**

```javascript
const getDateRangePreset = (preset) => {
  const today = new Date();
  const ranges = {
    today: {
      start: formatDate(today),
      end: formatDate(today)
    },
    yesterday: {
      start: formatDate(subDays(today, 1)),
      end: formatDate(subDays(today, 1))
    },
    thisWeek: {
      start: formatDate(startOfWeek(today)),
      end: formatDate(endOfWeek(today))
    },
    thisMonth: {
      start: formatDate(startOfMonth(today)),
      end: formatDate(endOfMonth(today))
    },
    last7Days: {
      start: formatDate(subDays(today, 7)),
      end: formatDate(today)
    },
    last30Days: {
      start: formatDate(subDays(today, 30)),
      end: formatDate(today)
    },
    custom: null // User selects custom dates
  };
  
  return ranges[preset];
};
```

### 3. Displaying Sales Cards/List Items

**Recommended Data to Display:**

```javascript
// Sales list item component
const SalesHistoryCard = ({ sale }) => (
  <Card onPress={() => navigateToDetails(sale.id)}>
    <Row>
      <InvoiceNumber>{sale.invoice_no}</InvoiceNumber>
      <StatusBadge status={sale.status}>{sale.status}</StatusBadge>
    </Row>
    
    <CustomerInfo>
      <CustomerIcon />
      <CustomerName>{sale.customer_name}</CustomerName>
    </CustomerInfo>
    
    <Row>
      <DateInfo>
        <CalendarIcon />
        <DateText>{formatDate(sale.document_date)}</DateText>
      </DateInfo>
      
      <Amount>{formatCurrency(sale.total_amount)}</Amount>
    </Row>
    
    <Row>
      <PaymentMethod>
        <PaymentIcon />
        {sale.payment_method_name || "Unpaid"}
      </PaymentMethod>
      
      <PaymentStatus status={sale.payment_status}>
        {sale.payment_status}
      </PaymentStatus>
    </Row>
  </Card>
);
```

### 4. Implementing Pagination

**Infinite Scroll Pattern:**

```javascript
const useSalesHistory = () => {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({});

  const loadMore = async () => {
    if (loading || !hasMore) return;
    
    setLoading(true);
    try {
      const response = await fetchSalesHistory({ 
        ...filters, 
        page 
      });
      
      setSales(prev => [...prev, ...response.results]);
      setHasMore(!!response.next);
      setPage(prev => prev + 1);
    } catch (error) {
      console.error('Error loading sales:', error);
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    setPage(1);
    setSales([]);
    setHasMore(true);
    await loadMore();
  };

  return { sales, loading, hasMore, loadMore, refresh, setFilters };
};
```

### 5. Fetching Sale Details

```javascript
const fetchSaleDetails = async (saleId) => {
  try {
    const response = await api.get(`/sales/${saleId}/`);
    return response.data;
  } catch (error) {
    console.error('Error fetching sale details:', error);
    throw error;
  }
};
```

### 6. Displaying Sale Details

**Detail Screen Structure:**

```javascript
const SaleDetailScreen = ({ saleId }) => {
  const [sale, setSale] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSaleDetails();
  }, [saleId]);

  const loadSaleDetails = async () => {
    try {
      const data = await fetchSaleDetails(saleId);
      setSale(data);
    } catch (error) {
      showError('Failed to load sale details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView>
      {/* Header Section */}
      <HeaderCard>
        <InvoiceNumber>{sale.invoice_no}</InvoiceNumber>
        <StatusBadge>{sale.status}</StatusBadge>
        
        <InfoRow label="Customer" value={sale.customer_name} />
        <InfoRow label="Date" value={formatDate(sale.document_date)} />
        <InfoRow label="Due Date" value={formatDate(sale.due_date)} />
        <InfoRow label="Payment Method" value={sale.payment_method_name} />
        <InfoRow label="Served By" value={sale.user_name} />
      </HeaderCard>

      {/* Line Items Section */}
      <SectionTitle>Items Sold</SectionTitle>
      {sale.lines.map((line) => (
        <LineItemCard key={line.id}>
          <ItemName>{line.item_name}</ItemName>
          <ItemCode>{line.item_no}</ItemCode>
          
          <Row>
            <Quantity>{line.quantity} {line.unit_of_measure}</Quantity>
            <UnitPrice>@ {formatCurrency(line.unit_price)}</UnitPrice>
          </Row>
          
          <LineTotal>{formatCurrency(line.total_amount)}</LineTotal>
        </LineItemCard>
      ))}

      {/* Totals Section */}
      <TotalsCard>
        <TotalRow label="Subtotal" value={sale.total_amount} />
        <TotalRow label="Discount" value="0.00" />
        <Divider />
        <GrandTotalRow label="Total" value={sale.total_amount} />
        <TotalRow label="Amount Received" value={sale.amount_received} />
        <TotalRow label="Change" value={sale.change_amount} />
      </TotalsCard>

      {/* Actions */}
      <ActionsSection>
        <ActionButton icon="print" onPress={handlePrint}>Print</ActionButton>
        <ActionButton icon="share" onPress={handleShare}>Share</ActionButton>
        <ActionButton icon="email" onPress={handleEmail}>Email</ActionButton>
      </ActionsSection>
    </ScrollView>
  );
};
```

---

## Data Synchronization Patterns

### 1. Pull-to-Refresh Pattern

```javascript
const SalesHistoryScreen = () => {
  const [refreshing, setRefreshing] = useState(false);
  const { sales, refresh } = useSalesHistory();

  const onRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  };

  return (
    <FlatList
      data={sales}
      renderItem={({ item }) => <SalesHistoryCard sale={item} />}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    />
  );
};
```

### 2. Real-time Updates

**When to Refresh:**
- User navigates back to Sales History screen
- User completes a new sale
- User applies new filters
- App comes to foreground

```javascript
useEffect(() => {
  const unsubscribe = navigation.addListener('focus', () => {
    refresh(); // Refresh when screen comes into focus
  });

  return unsubscribe;
}, [navigation]);
```

### 3. Offline Support (Optional)

```javascript
// Cache sales data locally
const cacheSales = async (sales) => {
  await AsyncStorage.setItem('cached_sales', JSON.stringify(sales));
};

// Load cached data on offline
const loadCachedSales = async () => {
  const cached = await AsyncStorage.getItem('cached_sales');
  return cached ? JSON.parse(cached) : [];
};

// Check network and load accordingly
const loadSales = async () => {
  if (isOnline) {
    const data = await fetchSalesHistory();
    await cacheSales(data.results);
    return data.results;
  } else {
    return await loadCachedSales();
  }
};
```

---

## Advanced Features

### 1. Sales Statistics Dashboard

```javascript
const SalesDashboard = ({ filters }) => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    loadStats();
  }, [filters]);

  const loadStats = async () => {
    try {
      const data = await api.get('/sales/summary/', {
        params: filters
      });
      setStats(data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  return (
    <DashboardGrid>
      <StatCard
        title="Total Sales"
        value={formatCurrency(stats?.total_sales || 0)}
        icon="cash"
        color="green"
      />
      <StatCard
        title="Total Invoices"
        value={stats?.total_invoices || 0}
        icon="receipt"
        color="blue"
      />
      <StatCard
        title="Products Sold"
        value={stats?.total_products || 0}
        icon="cube"
        color="orange"
      />
    </DashboardGrid>
  );
};
```

### 2. Export/Share Functionality

```javascript
const exportSalesData = async (sales) => {
  // Convert sales data to CSV or PDF
  const csvData = convertToCSV(sales);
  
  // Share or save the file
  await Share.share({
    title: 'Sales Report',
    message: 'Sales data export',
    url: csvData
  });
};
```

### 3. Advanced Filtering UI

```javascript
const SalesFilterModal = ({ visible, onApply, onClose }) => {
  const [dateRange, setDateRange] = useState('thisMonth');
  const [customer, setCustomer] = useState(null);
  const [status, setStatus] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState(null);

  const applyFilters = () => {
    const filters = {};
    
    if (dateRange !== 'all') {
      const range = getDateRangePreset(dateRange);
      if (range) {
        filters.dateRange = range;
      }
    }
    
    if (customer) filters.customer = customer;
    if (status) filters.status = status;
    if (paymentMethod) filters.paymentMethod = paymentMethod;
    
    onApply(filters);
    onClose();
  };

  return (
    <Modal visible={visible}>
      <FilterSection title="Date Range">
        <FilterOption 
          label="Today" 
          selected={dateRange === 'today'}
          onPress={() => setDateRange('today')}
        />
        <FilterOption 
          label="This Week" 
          selected={dateRange === 'thisWeek'}
          onPress={() => setDateRange('thisWeek')}
        />
        <FilterOption 
          label="This Month" 
          selected={dateRange === 'thisMonth'}
          onPress={() => setDateRange('thisMonth')}
        />
        <FilterOption 
          label="Last 30 Days" 
          selected={dateRange === 'last30Days'}
          onPress={() => setDateRange('last30Days')}
        />
        <FilterOption 
          label="Custom" 
          selected={dateRange === 'custom'}
          onPress={() => setDateRange('custom')}
        />
      </FilterSection>

      <FilterSection title="Status">
        <FilterOption 
          label="All" 
          selected={!status}
          onPress={() => setStatus(null)}
        />
        <FilterOption 
          label="Draft" 
          selected={status === 'Draft'}
          onPress={() => setStatus('Draft')}
        />
        <FilterOption 
          label="Posted" 
          selected={status === 'Posted'}
          onPress={() => setStatus('Posted')}
        />
      </FilterSection>

      <FilterSection title="Payment Status">
        <FilterOption 
          label="All" 
          selected={!paymentMethod}
          onPress={() => setPaymentMethod(null)}
        />
        <FilterOption 
          label="Paid" 
          selected={paymentMethod !== 'not_paid' && paymentMethod !== null}
          onPress={() => setPaymentMethod('')}
        />
        <FilterOption 
          label="Unpaid" 
          selected={paymentMethod === 'not_paid'}
          onPress={() => setPaymentMethod('not_paid')}
        />
      </FilterSection>

      <ButtonRow>
        <ClearButton onPress={clearFilters}>Clear</ClearButton>
        <ApplyButton onPress={applyFilters}>Apply Filters</ApplyButton>
      </ButtonRow>
    </Modal>
  );
};
```

---

## Best Practices

### 1. Performance Optimization

- **Use pagination** instead of loading all sales at once
- **Implement caching** for frequently accessed data
- **Lazy load** line items only when viewing details
- **Optimize images** if displaying product images
- **Debounce search** input to reduce API calls

### 2. Error Handling

```javascript
const handleSalesError = (error) => {
  if (error.response?.status === 403) {
    showError('You don\'t have permission to view sales history');
  } else if (error.response?.status === 404) {
    showError('Sale not found');
  } else if (!navigator.onLine) {
    showError('No internet connection. Showing cached data.');
  } else {
    showError('Failed to load sales. Please try again.');
  }
};
```

### 3. Loading States

```javascript
const LoadingState = () => (
  <View>
    <SkeletonCard />
    <SkeletonCard />
    <SkeletonCard />
  </View>
);

const EmptyState = () => (
  <CenteredView>
    <EmptyIcon />
    <EmptyText>No sales found</EmptyText>
    <EmptySubtext>Try adjusting your filters</EmptySubtext>
  </CenteredView>
);
```

### 4. Security Considerations

- **Always include JWT token** in API requests
- **Handle token expiration** gracefully
- **Don't cache sensitive data** unencrypted
- **Validate user permissions** before showing actions
- **Log out user** if permission errors occur

### 5. User Experience

- **Show loading indicators** during data fetch
- **Provide meaningful error messages**
- **Enable pull-to-refresh** for manual updates
- **Remember filter preferences** across sessions
- **Show empty states** when no data
- **Highlight unpaid invoices** for attention

---

## Common Use Cases

### 1. Today's Sales Report

```javascript
const getTodaysSales = async () => {
  const today = formatDate(new Date());
  const filters = {
    document_date__gte: today,
    document_date__lte: today,
    status: 'Posted'
  };
  
  const sales = await fetchSalesHistory(filters);
  const summary = await api.get('/sales/summary/', { params: filters });
  
  return { sales, summary };
};
```

### 2. Unpaid Invoices

```javascript
const getUnpaidInvoices = async () => {
  const filters = {
    payment_method: 'not_paid',
    status: 'Posted'
  };
  
  return await fetchSalesHistory(filters);
};
```

### 3. Customer Purchase History

```javascript
const getCustomerPurchases = async (customerId) => {
  const filters = {
    customer: customerId,
    ordering: '-document_date'
  };
  
  return await fetchSalesHistory(filters);
};
```

### 4. Month-End Report

```javascript
const getMonthEndReport = async (year, month) => {
  const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
  const endDate = formatDate(endOfMonth(new Date(year, month - 1)));
  
  const filters = {
    document_date__gte: startDate,
    document_date__lte: endDate,
    status: 'Posted'
  };
  
  const sales = await fetchSalesHistory(filters);
  const summary = await api.get('/sales/summary/', { params: filters });
  
  return { sales, summary };
};
```

---

## Testing Checklist

### Functional Testing

- [ ] Sales list loads correctly
- [ ] Pagination works (load more)
- [ ] Filters apply correctly
- [ ] Search functionality works
- [ ] Sale details display properly
- [ ] Pull-to-refresh updates data
- [ ] Empty states show when no data
- [ ] Error messages display appropriately

### Permission Testing

- [ ] Users without READ permission see error
- [ ] Users without permission can't access details
- [ ] Summary endpoint checks correct permission (10004)
- [ ] Token expiration handled gracefully

### Performance Testing

- [ ] List loads in < 2 seconds
- [ ] Details load in < 1 second
- [ ] Smooth scrolling with 100+ items
- [ ] Filters respond instantly
- [ ] No memory leaks on list scroll

### UI/UX Testing

- [ ] Loading indicators show during fetch
- [ ] Success/error messages are clear
- [ ] Filter modal is intuitive
- [ ] Date picker works correctly
- [ ] Cards/items are readable
- [ ] Actions (print, share) work
- [ ] Offline mode shows cached data

---

## Implementation Files Reference

### Backend Files

- **ViewSet**: `sales/views.py` (SalesViewSet, lines 360-792)
- **Serializer**: `sales/serializers.py` (SalesInvoiceSerializer)
- **Models**: `sales/models.py` (SalesInvoice, SalesInvoiceLine)
- **URLs**: `sales/urls.py` (router registration)
- **Filters**: `sales/views.py` (SalesFilter, lines 186-198)

### Frontend Patterns

- **Customer Creation**: Reference pattern in `customer-creation-guide.md`
- **Item Management**: Reference pattern in existing items implementation
- **Prepayment Lines**: Similar card+lines pattern in `prepayment_card_lines` rule

---

## Additional Notes

### Payment Status Logic

The `payment_status` field is computed based on:
- `status`: "Draft" or "Posted"
- `payment_method`: Present or null
- `amount_received`: Amount paid

Possible values:
- `"Paid"`: Posted with payment method and full amount received
- `"Unpaid"`: Posted without payment method
- `"Draft"`: Not yet posted

### Date Field Meanings

- `document_date`: Date of the sale transaction
- `posting_date`: Date when the sale was posted to accounting
- `vat_date`: Date for VAT calculation purposes
- `due_date`: Payment due date

### Line Amount Calculation

```
line_amount = quantity × unit_price
total_amount = line_amount - line_discount_amount
```

### Status Workflow

```
Draft → Posted
```

Once posted, sales create accounting and inventory entries and cannot be edited directly.

---

## Support & Troubleshooting

### Common Issues

1. **403 Forbidden Error**
   - Check user has READ permission on Page Object 10002
   - Verify JWT token is valid and not expired
   - Ensure user belongs to User Group with correct Permission Sets

2. **Empty Results**
   - Check filters aren't too restrictive
   - Verify date range format (YYYY-MM-DD)
   - Ensure customer/payment_method IDs exist

3. **Slow Loading**
   - Reduce page_size if too large
   - Check network connection
   - Verify backend performance

4. **Missing Line Items**
   - Ensure sale includes `lines` in response
   - Check serializer includes nested lines
   - Verify prefetch_related on queryset

---

## Conclusion

This guide provides a comprehensive foundation for implementing Sales History in the ZentroApp mobile application. Follow the patterns established here for consistency with the rest of the application, and refer to the backend implementation files for specific field names and data structures.

For questions or issues, consult the backend API documentation or the development team.


