# Purchase Invoice Creation Guide

## Overview

This guide explains how to implement **Purchase Invoice Creation and Management** in the ZentroApp mobile application. This is a **high-level implementation guide** that focuses on the API endpoints, data structure, and workflows for creating, updating, and managing purchase invoices (stock receiving) from vendors.

## Purchase Invoice Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES PURCHASE INVOICE CREATION                 │
│ - Mobile: Tap "New Purchase" or "Receive Stock"          │
│ - Display purchase creation form                         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: INITIALIZE PURCHASE FORM                     │
│ - Create local purchase object with default values       │
│ - Set document_date to today                             │
│ - Initialize empty lines array                           │
│ - Generate temporary client_id for tracking              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER SELECTS VENDOR (Required)                           │
│ - Open vendor picker/search modal                        │
│ - Search and select vendor                               │
│ - Vendor name is REQUIRED for creation                   │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS HEADER FIELDS                                 │
│ - Document Date (defaults to today)                      │
│ - Vendor Invoice No (optional)                           │
│ - Contact Person (optional)                              │
│ - Payment Method (optional)                              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: CREATE PURCHASE (UPSERT)                     │
│ - Send POST to /api/purchases/upsert/                    │
│ - Include vendor and header fields                       │
│ - No lines yet (will be added separately)                │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: CREATE PURCHASE INVOICE                         │
│ - Validate vendor exists                                 │
│ - Auto-generate invoice_no (from no-series)              │
│ - Set status to "Open" (Draft)                           │
│ - Create purchase record                                 │
│ - Return purchase with system_id and id                  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: RECEIVE RESPONSE                             │
│ - Update local purchase with server response             │
│ - Save system_id and id for future updates               │
│ - Enable line items addition                             │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER ADDS LINE ITEMS                                     │
│ - Tap "Add Item" button                                  │
│ - Open item picker/scanner                               │
│ - Select item or scan barcode                            │
│ - Set quantity and unit cost                             │
│ - Select unit of measure (UOM)                           │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: UPDATE LINES (Auto-save)                     │
│ - Send POST to /api/purchases/{id}/update_lines/         │
│ - Include all lines (existing + new)                     │
│ - Lines with id: update, without id: create              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS LINE UPDATES                            │
│ - Validate items exist                                   │
│ - Get/create UnitOfMeasure and ItemUnitOfMeasure         │
│ - Calculate line totals (quantity × unit_cost)           │
│ - Save lines and recalculate purchase total              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: UPDATE UI                                    │
│ - Refresh purchase with updated lines                    │
│ - Update total amount display                            │
│ - Show line items in list                                │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER CONTINUES EDITING                                   │
│ - Add more items                                         │
│ - Edit quantities/costs (triggers auto-save)             │
│ - Delete lines (send with "deleted": true)               │
│ - Each change calls update_lines endpoint                │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER SAVES/POSTS PURCHASE                                │
│ - Review purchase summary                                │
│ - Tap "Save Draft" or "Post Purchase"                    │
│ - Post: Send POST to /api/purchases/{id}/post_purchase/  │
│ - Save: Already auto-saved, just exit                    │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: POST PURCHASE (If requested)                    │
│ - Change status from "Open" to "Posted"                  │
│ - Create accounting entries (Vendor Ledger, GL)          │
│ - Create inventory entries (Item Ledger)                 │
│ - Update vendor balance                                  │
│ - Lock invoice from further edits                        │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ MOBILE APP: CONFIRM & NAVIGATE                           │
│ - Show success message                                   │
│ - Navigate back to purchase list                         │
│ - Refresh purchase list                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Backend API Structure

### Main Endpoints

#### 1. Create/Update Purchase Invoice (Upsert)

```
POST /api/purchases/upsert/
```

**Purpose:** Create a new purchase invoice or update an existing one based on `system_id` or `id`.

**Authentication & Permissions:**
- **Authentication**: Required (JWT Token)
- **Permission Check**: Will be implemented (similar to sales)
- **Permission Source**: User's permission sets via User Groups

**Request Payload (Create New):**

```json
{
  "vendor_name": "ABC Suppliers Ltd",  // REQUIRED for creation
  "vendor": 15,                         // Vendor ID (optional if vendor_name provided)
  "document_date": "2024-12-06",        // Defaults to today if not provided
  "posting_date": "2024-12-06",         // Defaults to today if not provided
  "vat_date": "2024-12-06",            // Defaults to today if not provided
  "due_date": "2024-12-20",            // Optional
  "vendor_invoice_no": "INV-2024-001", // Optional, vendor's invoice number
  "contact_person": "John Doe",        // Optional
  "payment_method": 1,                 // Optional, Payment Method ID
  "status": "Open"                     // Optional, defaults to "Open"
}
```

**Request Payload (Update Existing):**

```json
{
  "system_id": "uuid-string",          // Use system_id to identify purchase
  "id": 123,                           // Or use numeric id
  "vendor": 15,                        // Can update vendor
  "document_date": "2024-12-06",
  "vendor_invoice_no": "INV-2024-001",
  "payment_method": 2,
  // ... other fields to update
}
```

**Request Payload (Delete):**

```json
{
  "system_id": "uuid-string",          // Or use "id"
  "deleted": true                      // Marks for deletion
}
```

**Response Format (Success - Create):**

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "invoice_no": "PI-20241206001",      // Auto-generated
  "vendor": 15,
  "vendor_name": "ABC Suppliers Ltd",
  "contact_person": "John Doe",
  "document_date": "2024-12-06",
  "posting_date": "2024-12-06",
  "vat_date": "2024-12-06",
  "due_date": "2024-12-20",
  "vendor_invoice_no": "INV-2024-001",
  "status": "Open",
  "payment_method": 1,
  "payment_method_name": "Cash",
  "payment_method_details": {
    "id": 1,
    "code": "CASH",
    "description": "Cash"
  },
  "total_amount": "0.00",              // No lines yet
  "created_at": "2024-12-06T10:30:00Z",
  "updated_at": "2024-12-06T10:30:00Z",
  "lines": []                          // Empty initially
}
```

**Response Format (Error):**

```json
{
  "vendor_name": "Vendor name is required"
}
```

**Important Notes:**
- For **creating** a new purchase: `vendor_name` is REQUIRED
- For **updating**: Include either `system_id` or `id` to identify the purchase
- For **deleting**: Set `deleted: true` along with identifier

---

#### 2. Update Purchase Lines

```
POST /api/purchases/{id}/update_lines/
```

**Purpose:** Add, update, or delete line items in a purchase invoice. This is the core endpoint for building the purchase.

**Path Parameters:**
- `id`: Numeric ID or system_id of the purchase invoice

**Request Payload:**

```json
{
  "lines": [
    {
      // Create new line (no id field)
      "item_no": "ITM-000001",
      "item_name": "Product A",
      "item_system_id": "item-uuid",
      "quantity": 10,
      "unit_cost": 50000,
      "unit_of_measure": "PCS",
      "description": "Product A - Bulk Order"
    },
    {
      // Update existing line (has id)
      "id": 456,
      "system_id": "line-uuid",
      "item_no": "ITM-000002",
      "item_name": "Product B",
      "quantity": 5,
      "unit_cost": 75000,
      "unit_of_measure": "PCS",
      "description": "Product B"
    },
    {
      // Delete line (has id and deleted: true)
      "id": 457,
      "deleted": true
    }
  ]
}
```

**Line Data Fields:**

```javascript
{
  id: 456,                           // Required for update/delete, omit for create
  system_id: "uuid",                 // Line system ID (read-only)
  item_no: "ITM-000001",            // REQUIRED: Item number/code
  item_name: "Product A",           // REQUIRED: Item name (for lookup)
  item_system_id: "uuid",           // Item's system ID (optional)
  quantity: 10,                     // REQUIRED: Quantity to purchase
  unit_cost: 50000,                 // REQUIRED: Cost per unit
  unit_of_measure: "PCS",           // REQUIRED: UOM code (e.g., "PCS", "KG", "BOX")
  description: "Description",       // Optional: Line description
  deleted: false                    // Set to true to delete the line
}
```

**Response Format:**

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "invoice_no": "PI-20241206001",
  "vendor": 15,
  "vendor_name": "ABC Suppliers Ltd",
  "document_date": "2024-12-06",
  "status": "Open",
  "total_amount": "875000.00",      // Recalculated from lines
  "lines": [
    {
      "id": 456,
      "system_id": "line-uuid",
      "item": "ITM-000001",
      "item_name": "Product A",
      "item_no": "ITM-000001",
      "quantity": "10.00",
      "unit_cost": "50000.00",
      "total_amount": "500000.00",   // quantity × unit_cost
      "description": "Product A - Bulk Order",
      "unit_of_measure": "PCS",
      "location_code": "MAIN",
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
      "id": 458,
      "system_id": "line-uuid-2",
      "item": "ITM-000002",
      "item_name": "Product B",
      "item_no": "ITM-000002",
      "quantity": "5.00",
      "unit_cost": "75000.00",
      "total_amount": "375000.00",
      "description": "Product B",
      "unit_of_measure": "PCS",
      "location_code": "MAIN",
      "uom_options": []
    }
  ],
  "created_at": "2024-12-06T10:30:00Z",
  "updated_at": "2024-12-06T10:35:00Z"
}
```

**Important Notes:**
- **Item lookup**: Backend finds item using `item_name` AND `item_no`
- **UOM handling**: Backend auto-creates UnitOfMeasure and ItemUnitOfMeasure if they don't exist
- **Location**: Automatically set from user's `dimension_1` (branch/location)
- **Total calculation**: `total_amount = quantity × unit_cost` (auto-calculated)
- **Deleted lines**: Must have `id` and `deleted: true`

---

#### 3. Post Purchase Invoice

```
POST /api/purchases/{id}/post_purchase/
```

**Purpose:** Post the purchase invoice to finalize it. This creates accounting and inventory entries and locks the invoice from further editing.

**Path Parameters:**
- `id`: Numeric ID or system_id of the purchase invoice

**Request Payload:**
```json
{}  // No body required
```

**Response Format:**

```json
{
  "message": "Purchase invoice posted successfully",
  "purchase": {
    "id": 123,
    "invoice_no": "PI-20241206001",
    "status": "Posted",              // Changed from "Open" to "Posted"
    "total_amount": "875000.00",
    // ... full purchase details
  }
}
```

**What Happens When Posted:**
1. Status changes from "Open" to "Posted"
2. Creates Vendor Ledger entries (increases vendor balance)
3. Creates General Ledger entries (accounting)
4. Creates Item Ledger entries (increases inventory)
5. Invoice becomes read-only (cannot edit lines)

---

#### 4. Get Purchase Details

```
GET /api/purchases/{id}/
```

**Purpose:** Retrieve full details of a single purchase invoice.

**Path Parameters:**
- `id`: Numeric ID or system_id

**Response Format:**
Same as upsert response, including all lines.

---

#### 5. List Purchases

```
GET /api/purchases/
```

**Purpose:** Get paginated list of all purchase invoices with filtering.

**Query Parameters:**

```javascript
{
  // Pagination
  page: 1,
  page_size: 50,
  
  // Search
  search: "vendor name",           // Search by vendor name or invoice number
  
  // Filters
  vendor: 15,                      // Filter by vendor ID
  status: "Open",                  // Filter by status: "Open" or "Posted"
  
  // Date filters
  document_date__gte: "2024-12-01",
  document_date__lte: "2024-12-31",
  
  // Ordering
  ordering: "-created_at"          // Order by field (- for descending)
}
```

**Response Format:**

```json
{
  "count": 50,
  "next": "http://api.zentroapp.app/api/purchases/?page=2",
  "previous": null,
  "results": [
    {
      // Purchase invoice objects (same structure as detail)
    }
  ]
}
```

---

## Mobile App Implementation Guide

### 1. Creating a New Purchase Invoice

**Step-by-Step Implementation:**

```javascript
// Step 1: Initialize purchase creation
const initiatePurchaseCreation = () => {
  const newPurchase = {
    client_id: generateClientId(),        // Local tracking ID
    vendor: null,
    vendor_name: '',
    document_date: formatDate(new Date()),
    posting_date: formatDate(new Date()),
    vat_date: formatDate(new Date()),
    due_date: formatDate(addDays(new Date(), 14)), // 14 days from today
    vendor_invoice_no: '',
    contact_person: '',
    payment_method: null,
    status: 'Open',
    lines: []
  };
  
  return newPurchase;
};

// Step 2: Select vendor (REQUIRED)
const selectVendor = async (vendorId) => {
  try {
    const vendor = await api.get(`/vendors/${vendorId}/`);
    
    return {
      vendor: vendor.id,
      vendor_name: vendor.name,
      contact_person: vendor.contact || ''
    };
  } catch (error) {
    console.error('Error fetching vendor:', error);
    throw error;
  }
};

// Step 3: Create purchase on server
const createPurchase = async (purchaseData) => {
  try {
    const response = await api.post('/purchases/upsert/', {
      vendor_name: purchaseData.vendor_name,  // REQUIRED
      vendor: purchaseData.vendor,
      document_date: purchaseData.document_date,
      posting_date: purchaseData.posting_date,
      vat_date: purchaseData.vat_date,
      due_date: purchaseData.due_date,
      vendor_invoice_no: purchaseData.vendor_invoice_no,
      contact_person: purchaseData.contact_person,
      payment_method: purchaseData.payment_method,
    });
    
    // Save the returned id and system_id for future updates
    return response.data;
  } catch (error) {
    if (error.response?.data?.vendor_name) {
      throw new Error('Vendor is required to create a purchase');
    }
    throw error;
  }
};
```

### 2. Adding Line Items

```javascript
// Add/Update purchase lines
const updatePurchaseLines = async (purchaseId, lines) => {
  try {
    // Prepare lines data
    const linesData = lines.map(line => ({
      id: line.id,                      // Include for updates, omit for new lines
      system_id: line.system_id,
      item_no: line.item_no,
      item_name: line.item_name,
      item_system_id: line.item_system_id,
      quantity: line.quantity,
      unit_cost: line.unit_cost,
      unit_of_measure: line.unit_of_measure || 'PCS',
      description: line.description || line.item_name,
      deleted: line.deleted || false
    }));
    
    const response = await api.post(`/purchases/${purchaseId}/update_lines/`, {
      lines: linesData
    });
    
    return response.data;
  } catch (error) {
    console.error('Error updating lines:', error);
    throw error;
  }
};

// Add single item to purchase
const addItemToPurchase = async (purchaseId, item, quantity, unitCost) => {
  const newLine = {
    item_no: item.no,
    item_name: item.item_name,
    item_system_id: item.system_id,
    quantity: quantity,
    unit_cost: unitCost,
    unit_of_measure: item.base_unit_of_measure || 'PCS',
    description: item.item_name
  };
  
  // Get current lines and add new one
  const currentLines = await getCurrentLines(purchaseId);
  const updatedLines = [...currentLines, newLine];
  
  return await updatePurchaseLines(purchaseId, updatedLines);
};
```

### 3. Auto-Save Pattern (Save on Blur)

```javascript
const PurchaseLineItem = ({ line, purchaseId, onUpdate }) => {
  const [localQuantity, setLocalQuantity] = useState(line.quantity);
  const [localUnitCost, setLocalUnitCost] = useState(line.unit_cost);
  const [isSaving, setIsSaving] = useState(false);
  
  const saveChanges = async () => {
    if (localQuantity === line.quantity && localUnitCost === line.unit_cost) {
      return; // No changes
    }
    
    setIsSaving(true);
    try {
      const updatedLine = {
        ...line,
        quantity: localQuantity,
        unit_cost: localUnitCost
      };
      
      await updatePurchaseLines(purchaseId, [updatedLine]);
      onUpdate();
    } catch (error) {
      showError('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };
  
  return (
    <LineItemRow>
      <ItemInfo>
        <ItemName>{line.item_name}</ItemName>
        <ItemCode>{line.item_no}</ItemCode>
      </ItemInfo>
      
      <Input
        value={localQuantity}
        onChange={setLocalQuantity}
        onBlur={saveChanges}              // Auto-save on blur
        keyboardType="numeric"
        placeholder="Qty"
      />
      
      <Input
        value={localUnitCost}
        onChange={setLocalUnitCost}
        onBlur={saveChanges}              // Auto-save on blur
        keyboardType="numeric"
        placeholder="Cost"
      />
      
      <LineTotal>
        {formatCurrency(localQuantity * localUnitCost)}
      </LineTotal>
      
      {isSaving && <SavingIndicator />}
    </LineItemRow>
  );
};
```

### 4. Complete Purchase Creation Screen

```javascript
const PurchaseCreationScreen = ({ navigation, route }) => {
  const [purchase, setPurchase] = useState(null);
  const [vendor, setVendor] = useState(null);
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Initialize purchase
  useEffect(() => {
    const newPurchase = initiatePurchaseCreation();
    setPurchase(newPurchase);
  }, []);

  // Step 1: Select vendor
  const handleVendorSelect = async (selectedVendor) => {
    setVendor(selectedVendor);
    setPurchase(prev => ({
      ...prev,
      vendor: selectedVendor.id,
      vendor_name: selectedVendor.name,
      contact_person: selectedVendor.contact || ''
    }));
  };

  // Step 2: Create purchase on server
  const handleCreatePurchase = async () => {
    if (!vendor) {
      showError('Please select a vendor first');
      return;
    }
    
    setLoading(true);
    try {
      const createdPurchase = await createPurchase(purchase);
      setPurchase(createdPurchase);
      showSuccess('Purchase created successfully');
    } catch (error) {
      showError(error.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Add items
  const handleAddItem = async (item) => {
    if (!purchase.id) {
      showError('Please create the purchase first');
      return;
    }
    
    setSaving(true);
    try {
      const updatedPurchase = await addItemToPurchase(
        purchase.id,
        item,
        1,                                    // Default quantity
        parseFloat(item.unit_cost || 0)      // Default cost from item
      );
      
      setPurchase(updatedPurchase);
      setLines(updatedPurchase.lines);
      showSuccess('Item added successfully');
    } catch (error) {
      showError('Failed to add item');
    } finally {
      setSaving(false);
    }
  };

  // Step 4: Delete line
  const handleDeleteLine = async (lineId) => {
    setSaving(true);
    try {
      const updatedLines = lines.map(line =>
        line.id === lineId ? { ...line, deleted: true } : line
      );
      
      const updatedPurchase = await updatePurchaseLines(purchase.id, updatedLines);
      setPurchase(updatedPurchase);
      setLines(updatedPurchase.lines.filter(l => !l.deleted));
      showSuccess('Item removed');
    } catch (error) {
      showError('Failed to remove item');
    } finally {
      setSaving(false);
    }
  };

  // Step 5: Post purchase
  const handlePostPurchase = async () => {
    if (lines.length === 0) {
      showError('Please add at least one item');
      return;
    }
    
    Alert.alert(
      'Post Purchase',
      'Are you sure? This will finalize the purchase and cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Post',
          onPress: async () => {
            setLoading(true);
            try {
              await api.post(`/purchases/${purchase.id}/post_purchase/`);
              showSuccess('Purchase posted successfully');
              navigation.goBack();
            } catch (error) {
              showError('Failed to post purchase');
            } finally {
              setLoading(false);
            }
          }
        }
      ]
    );
  };

  return (
    <Screen>
      <ScrollView>
        {/* Header Section */}
        <HeaderCard>
          <Title>New Purchase Invoice</Title>
          {purchase?.invoice_no && (
            <InvoiceNumber>{purchase.invoice_no}</InvoiceNumber>
          )}
        </HeaderCard>

        {/* Vendor Selection */}
        <Section>
          <SectionTitle>Vendor *</SectionTitle>
          {vendor ? (
            <VendorCard>
              <VendorName>{vendor.name}</VendorName>
              <VendorCode>{vendor.no}</VendorCode>
              <ChangeButton onPress={() => openVendorPicker()}>
                Change
              </ChangeButton>
            </VendorCard>
          ) : (
            <SelectVendorButton onPress={openVendorPicker}>
              <Icon name="add" />
              <ButtonText>Select Vendor</ButtonText>
            </SelectVendorButton>
          )}
        </Section>

        {/* Header Fields */}
        {vendor && (
          <Section>
            <DateField
              label="Document Date"
              value={purchase?.document_date}
              onChange={(date) => setPurchase(prev => ({ ...prev, document_date: date }))}
            />
            
            <TextField
              label="Vendor Invoice No"
              value={purchase?.vendor_invoice_no}
              onChange={(value) => setPurchase(prev => ({ ...prev, vendor_invoice_no: value }))}
              placeholder="Vendor's invoice number"
            />
            
            <PaymentMethodPicker
              label="Payment Method"
              value={purchase?.payment_method}
              onChange={(method) => setPurchase(prev => ({ ...prev, payment_method: method }))}
            />
          </Section>
        )}

        {/* Create Purchase Button (if not created yet) */}
        {vendor && !purchase?.id && (
          <CreateButton onPress={handleCreatePurchase} loading={loading}>
            Create Purchase
          </CreateButton>
        )}

        {/* Line Items Section */}
        {purchase?.id && (
          <>
            <Section>
              <SectionTitle>Items</SectionTitle>
              
              {lines.map((line) => (
                <PurchaseLineItem
                  key={line.id || line.client_id}
                  line={line}
                  purchaseId={purchase.id}
                  onUpdate={() => {/* Refresh purchase */}}
                  onDelete={() => handleDeleteLine(line.id)}
                />
              ))}
              
              <AddItemButton onPress={openItemPicker}>
                <Icon name="add" />
                <ButtonText>Add Item</ButtonText>
              </AddItemButton>
            </Section>

            {/* Totals */}
            <TotalsSection>
              <TotalRow>
                <TotalLabel>Total Amount</TotalLabel>
                <TotalValue>{formatCurrency(purchase.total_amount)}</TotalValue>
              </TotalRow>
            </TotalsSection>

            {/* Actions */}
            <ActionsSection>
              <SaveDraftButton onPress={() => navigation.goBack()}>
                Save Draft
              </SaveDraftButton>
              
              <PostButton 
                onPress={handlePostPurchase}
                disabled={lines.length === 0}
                loading={loading}
              >
                Post Purchase
              </PostButton>
            </ActionsSection>
          </>
        )}
      </ScrollView>

      {/* Modals */}
      <VendorPickerModal
        visible={vendorPickerVisible}
        onSelect={handleVendorSelect}
        onClose={() => setVendorPickerVisible(false)}
      />
      
      <ItemPickerModal
        visible={itemPickerVisible}
        onSelect={handleAddItem}
        onClose={() => setItemPickerVisible(false)}
      />
      
      {saving && <LoadingOverlay />}
    </Screen>
  );
};
```

---

## Advanced Features

### 1. Barcode Scanner Integration

```javascript
const handleBarcodeScan = async (barcode) => {
  try {
    // Find item by barcode
    const response = await api.get('/items/', {
      params: { search: barcode }
    });
    
    if (response.data.results.length > 0) {
      const item = response.data.results[0];
      await handleAddItem(item);
    } else {
      showError('Item not found');
    }
  } catch (error) {
    showError('Failed to scan item');
  }
};

const ScannerButton = ({ onScan }) => (
  <IconButton
    icon="barcode-scan"
    onPress={() => openBarcodeScanner(onScan)}
  >
    Scan Item
  </IconButton>
);
```

### 2. Quick Add from Item List

```javascript
const ItemQuickAdd = ({ item, onAdd }) => (
  <ItemCard>
    <ItemInfo>
      <ItemName>{item.item_name}</ItemName>
      <ItemCode>{item.no}</ItemCode>
      <ItemPrice>Cost: {formatCurrency(item.unit_cost)}</ItemPrice>
    </ItemInfo>
    
    <QuickAddButton onPress={() => onAdd(item, 1, item.unit_cost)}>
      <Icon name="add" />
    </QuickAddButton>
  </ItemCard>
);
```

### 3. Bulk Item Import

```javascript
const importFromFile = async (fileData) => {
  // Parse CSV or Excel file
  const items = parseImportFile(fileData);
  
  // Validate items exist
  const validatedItems = await validateItems(items);
  
  // Create lines in batch
  const linesData = validatedItems.map(item => ({
    item_no: item.no,
    item_name: item.name,
    quantity: item.quantity,
    unit_cost: item.cost,
    unit_of_measure: item.uom || 'PCS'
  }));
  
  await updatePurchaseLines(purchaseId, linesData);
};
```

### 4. Offline Support

```javascript
// Save purchase locally
const savePurchaseLocally = async (purchase) => {
  const localPurchases = await AsyncStorage.getItem('pending_purchases');
  const purchases = localPurchases ? JSON.parse(localPurchases) : [];
  
  purchases.push({
    ...purchase,
    syncStatus: 'pending',
    createdAt: new Date().toISOString()
  });
  
  await AsyncStorage.setItem('pending_purchases', JSON.stringify(purchases));
};

// Sync when online
const syncPendingPurchases = async () => {
  const localPurchases = await AsyncStorage.getItem('pending_purchases');
  if (!localPurchases) return;
  
  const purchases = JSON.parse(localPurchases);
  const synced = [];
  
  for (const purchase of purchases) {
    try {
      await createPurchase(purchase);
      synced.push(purchase);
    } catch (error) {
      console.error('Failed to sync purchase:', error);
    }
  }
  
  // Remove synced purchases
  const remaining = purchases.filter(p => !synced.includes(p));
  await AsyncStorage.setItem('pending_purchases', JSON.stringify(remaining));
};
```

---

## Best Practices

### 1. Validation

```javascript
const validatePurchase = (purchase) => {
  const errors = {};
  
  if (!purchase.vendor_name) {
    errors.vendor_name = 'Vendor is required';
  }
  
  if (purchase.lines.length === 0) {
    errors.lines = 'At least one item is required';
  }
  
  purchase.lines.forEach((line, index) => {
    if (!line.quantity || line.quantity <= 0) {
      errors[`line_${index}_quantity`] = 'Quantity must be greater than 0';
    }
    
    if (!line.unit_cost || line.unit_cost <= 0) {
      errors[`line_${index}_cost`] = 'Unit cost must be greater than 0';
    }
  });
  
  return errors;
};
```

### 2. Error Handling

```javascript
const handlePurchaseError = (error) => {
  if (error.response?.status === 400) {
    if (error.response.data.vendor_name) {
      showError('Please select a vendor');
    } else if (error.response.data.detail?.includes('Item')) {
      showError('One or more items not found');
    } else {
      showError('Invalid purchase data');
    }
  } else if (error.response?.status === 404) {
    showError('Purchase not found');
  } else if (!navigator.onLine) {
    showError('No internet. Purchase saved locally.');
    savePurchaseLocally(purchase);
  } else {
    showError('Failed to save purchase. Please try again.');
  }
};
```

### 3. Auto-Save Implementation

```javascript
const useAutoSave = (purchaseId, data, delay = 1000) => {
  const timeoutRef = useRef(null);
  
  useEffect(() => {
    if (!purchaseId) return;
    
    // Clear previous timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Set new timeout
    timeoutRef.current = setTimeout(async () => {
      try {
        await updatePurchaseLines(purchaseId, data);
      } catch (error) {
        console.error('Auto-save failed:', error);
      }
    }, delay);
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [purchaseId, data, delay]);
};
```

### 4. Loading States

```javascript
const LoadingStates = {
  CreatingPurchase: () => (
    <LoadingView>
      <Spinner />
      <LoadingText>Creating purchase invoice...</LoadingText>
    </LoadingView>
  ),
  
  AddingItem: () => (
    <LoadingView>
      <Spinner />
      <LoadingText>Adding item...</LoadingText>
    </LoadingView>
  ),
  
  PostingPurchase: () => (
    <LoadingView>
      <Spinner />
      <LoadingText>Posting purchase...</LoadingText>
      <LoadingSubtext>This may take a moment</LoadingSubtext>
    </LoadingView>
  )
};
```

---

## Common Use Cases

### 1. Quick Stock Receive (Single Item)

```javascript
const quickReceiveStock = async (vendorId, item, quantity, cost) => {
  // Create purchase
  const purchase = await createPurchase({
    vendor: vendorId,
    vendor_name: vendor.name,
    document_date: formatDate(new Date())
  });
  
  // Add item
  await addItemToPurchase(purchase.id, item, quantity, cost);
  
  // Post immediately
  await api.post(`/purchases/${purchase.id}/post_purchase/`);
  
  showSuccess('Stock received successfully');
};
```

### 2. Receive Against Purchase Order

```javascript
const receiveAgainstPO = async (purchaseOrderId) => {
  // Get PO details
  const po = await api.get(`/purchase-orders/${purchaseOrderId}/`);
  
  // Create purchase invoice from PO
  const purchase = await createPurchase({
    vendor: po.vendor,
    vendor_name: po.vendor_name,
    // ... copy other fields from PO
  });
  
  // Copy lines from PO
  const lines = po.lines.map(line => ({
    item_no: line.item_no,
    item_name: line.item_name,
    quantity: line.quantity,
    unit_cost: line.unit_cost,
    unit_of_measure: line.unit_of_measure
  }));
  
  await updatePurchaseLines(purchase.id, lines);
  
  return purchase;
};
```

### 3. Return Purchase (Credit Memo)

```javascript
const createPurchaseReturn = async (originalPurchaseId) => {
  // Get original purchase
  const original = await api.get(`/purchases/${originalPurchaseId}/`);
  
  // Create return with negative quantities
  const returnLines = original.lines.map(line => ({
    ...line,
    quantity: -line.quantity,  // Negative for return
    id: undefined,              // Don't copy IDs
    system_id: undefined
  }));
  
  const returnPurchase = await createPurchase({
    vendor: original.vendor,
    vendor_name: original.vendor_name,
    vendor_invoice_no: `RETURN-${original.invoice_no}`
  });
  
  await updatePurchaseLines(returnPurchase.id, returnLines);
  
  return returnPurchase;
};
```

---

## Testing Checklist

### Functional Testing

- [ ] Can create purchase with vendor
- [ ] Cannot create without vendor
- [ ] Can add line items
- [ ] Can update quantities/costs
- [ ] Can delete line items
- [ ] Auto-save works on blur
- [ ] Totals calculate correctly
- [ ] Can post purchase
- [ ] Posted purchase is read-only
- [ ] Vendor search works
- [ ] Item search works
- [ ] Barcode scanner works

### Data Validation

- [ ] Vendor is required
- [ ] Quantity must be > 0
- [ ] Unit cost must be > 0
- [ ] Valid UOM codes
- [ ] Items exist in system
- [ ] Duplicate lines handled

### Error Handling

- [ ] Network errors show message
- [ ] Validation errors display
- [ ] 404 errors handled
- [ ] Offline mode works
- [ ] Sync resumes when online

### Performance

- [ ] Page loads quickly
- [ ] Line updates are fast
- [ ] No lag when typing
- [ ] Smooth scrolling
- [ ] No memory leaks

---

## Conclusion

This guide provides a complete foundation for implementing Purchase Invoice creation in the mobile app. The key patterns are:

1. **Two-step creation**: Create header first, then add lines
2. **Vendor required**: Cannot create without selecting a vendor
3. **Auto-save lines**: Save on blur for smooth UX
4. **Item lookup**: Backend handles UOM and location automatically
5. **Post to finalize**: Posting creates accounting/inventory entries

Follow these patterns for consistency with the web application and optimal user experience.

For questions or issues, consult the backend implementation at:
- **Views**: `purchases/views.py` (PurchaseViewSet)
- **Serializers**: `purchases/serializers.py`
- **Models**: `purchases/models.py`


