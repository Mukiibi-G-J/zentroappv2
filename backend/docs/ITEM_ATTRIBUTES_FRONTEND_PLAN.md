# Item Attributes Frontend Implementation Plan

## Overview

This document outlines the frontend implementation plan for the Item Attributes system, following existing autosave patterns in the codebase.

## Key Principles

1. **Follow Autosave Pattern**: Each attribute entry saves independently on blur, just like other fields
2. **Keep It Simple**: One entry per attribute, no complex nested structures
3. **Auto-load Category Attributes**: When item category changes, automatically load and display category attributes
4. **Reuse Existing Patterns**: Use the same patterns as AutoSaveField components in expenses, customers, etc.

## Architecture

### Component Structure

```
Items.tsx (Main Form)
├── AutoSaveField (existing fields)
├── ItemAttributeSection (NEW)
    └── ItemAttributeEntryField (NEW) - One per attribute
        ├── Option Type → MultiSelect
        ├── Text Type → Input
        ├── Integer Type → Number Input
        ├── Decimal Type → Decimal Input
        └── Date Type → Date Input
```

### Data Flow

```
1. User selects Item Category
   ↓
2. Fetch category attributes from API
   ↓
3. Display attribute fields (one per attribute)
   ↓
4. User fills attribute values
   ↓
5. On blur → Auto-save individual attribute entry
   ↓
6. Update Redux store with saved entry
```

## Implementation Steps

### Step 1: Backend API Endpoints

**Location**: `zentro-backend/items/views.py` and `urls.py`

**Endpoints Needed**:

1. **Get Category Attributes**
   ```
   GET /api/items/categories/{category_code}/attributes/
   Response: { attributes: ItemAttribute[] }
   ```

2. **Get Item Attribute Entries**
   ```
   GET /api/items/{item_id}/attribute-entries/
   Response: { entries: ItemAttributeEntry[] }
   ```

3. **Create/Update Attribute Entry** (Upsert)
   ```
   POST /api/items/attribute-entries/upsert/
   Body: {
     item: string (system_id),
     attribute: number (id),
     selected_values?: number[],
     value_text?: string,
     value_integer?: number,
     value_decimal?: number,
     value_date?: string
   }
   Response: ItemAttributeEntry
   ```

4. **Delete Attribute Entry**
   ```
   DELETE /api/items/attribute-entries/{id}/
   ```

5. **Get All Attributes** (for manual addition)
   ```
   GET /api/items/attributes/
   Response: { results: ItemAttribute[] }
   ```

6. **Get Attribute Values** (for option type)
   ```
   GET /api/items/attributes/{attribute_id}/values/
   Response: { values: ItemAttributeValue[] }
   ```

### Step 2: TypeScript Types

**Location**: `zentro-frontend/src/views/items/@types/index.d.ts`

**Add Types**:

```typescript
export type ItemAttribute = {
  id: number;
  name: string;
  type: 'option' | 'text' | 'integer' | 'decimal' | 'date';
  blocked: boolean;
  values?: ItemAttributeValue[];
};

export type ItemAttributeValue = {
  id: number;
  value: string;
  blocked: boolean;
};

export type ItemAttributeEntry = {
  id?: number;
  system_id?: string;
  item: string; // item system_id
  attribute: number; // attribute id
  attribute_name?: string; // for display
  selected_values?: number[]; // array of ItemAttributeValue ids
  value_text?: string;
  value_integer?: number;
  value_decimal?: number;
  value_date?: string;
  display_value?: string; // computed from backend
};

// Add to Item type
export type Item = {
  // ... existing fields
  attribute_entries?: ItemAttributeEntry[];
};

// Add to ItemFormValues
export interface ItemFormValues {
  // ... existing fields
  attribute_entries?: ItemAttributeEntry[];
}
```

### Step 3: API Service Functions

**Location**: `zentro-frontend/src/services/ItemService.ts`

**Add Functions**:

```typescript
// Get attributes for a category
export const apiGetCategoryAttributes = (categoryCode: string) => {
  return ApiService.fetchData<{ attributes: ItemAttribute[] }>({
    url: `/categories/${categoryCode}/attributes/`,
    method: "get",
  });
};

// Get attribute entries for an item
export const apiGetItemAttributeEntries = (itemSystemId: string) => {
  return ApiService.fetchData<{ entries: ItemAttributeEntry[] }>({
    url: `/items/${itemSystemId}/attribute-entries/`,
    method: "get",
  });
};

// Upsert attribute entry (create or update)
export const apiUpsertAttributeEntry = (data: Partial<ItemAttributeEntry>) => {
  return ApiService.fetchData<ItemAttributeEntry>({
    url: "/items/attribute-entries/upsert/",
    method: "post",
    data,
  });
};

// Delete attribute entry
export const apiDeleteAttributeEntry = (id: number) => {
  return ApiService.fetchData<void>({
    url: `/items/attribute-entries/${id}/`,
    method: "delete",
  });
};

// Get all attributes (for manual addition)
export const apiGetAllAttributes = (params?: { search?: string }) => {
  return ApiService.fetchData<{ results: ItemAttribute[] }>({
    url: "/items/attributes/",
    method: "get",
    params,
  });
};

// Get values for an attribute
export const apiGetAttributeValues = (attributeId: number) => {
  return ApiService.fetchData<{ values: ItemAttributeValue[] }>({
    url: `/items/attributes/${attributeId}/values/`,
    method: "get",
  });
};
```

### Step 4: ItemAttributeEntryField Component

**Location**: `zentro-frontend/src/views/items/components/ItemAttributeEntryField.tsx`

**Pattern**: Follow `AutoSaveField` from expenses/customers

**Key Features**:
- Auto-save on blur
- Handle all 5 attribute types
- Show loading/saved states
- Error handling
- Create entry if item exists but entry doesn't
- Update entry if it exists

**Component Structure**:

```typescript
interface ItemAttributeEntryFieldProps {
  attribute: ItemAttribute;
  entry?: ItemAttributeEntry; // existing entry if any
  itemSystemId: string; // current item system_id
  attributeValues: ItemAttributeValue[]; // for option type
  setIsSaving: (saving: boolean) => void;
  setShowSaved: (saved: boolean) => void;
  onEntrySaved: (entry: ItemAttributeEntry) => void;
  onEntryDeleted?: (entryId: number) => void;
}

const ItemAttributeEntryField: React.FC<ItemAttributeEntryFieldProps> = ({
  attribute,
  entry,
  itemSystemId,
  attributeValues,
  setIsSaving,
  setShowSaved,
  onEntrySaved,
  onEntryDeleted,
}) => {
  // State for current value based on type
  const [currentValue, setCurrentValue] = useState(getInitialValue());
  
  // Handle save on blur
  const handleBlur = async () => {
    if (!itemSystemId) return; // Item must exist first
    
    // Build payload based on attribute type
    const payload = buildPayload();
    
    try {
      setIsSaving(true);
      const response = await apiUpsertAttributeEntry(payload);
      onEntrySaved(response.data);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (error) {
      // Handle error
    } finally {
      setIsSaving(false);
    }
  };
  
  // Render field based on type
  const renderField = () => {
    switch (attribute.type) {
      case 'option':
        return <MultiSelect ... />;
      case 'text':
        return <Input type="text" ... />;
      case 'integer':
        return <Input type="number" ... />;
      case 'decimal':
        return <Input type="number" step="0.01" ... />;
      case 'date':
        return <Input type="date" ... />;
    }
  };
  
  return (
    <FormItem label={attribute.name}>
      {renderField()}
      {entry && <DeleteButton onClick={handleDelete} />}
    </FormItem>
  );
};
```

### Step 5: ItemAttributeSection Component

**Location**: `zentro-frontend/src/views/items/components/ItemAttributeSection.tsx`

**Purpose**: Container that manages all attribute entries for an item

**Features**:
- Loads category attributes when category changes
- Displays all attribute fields
- Allows adding custom attributes (not in category)
- Manages entry state

**Component Structure**:

```typescript
interface ItemAttributeSectionProps {
  itemSystemId: string;
  categoryCode: string | null;
  existingEntries: ItemAttributeEntry[];
  setIsSaving: (saving: boolean) => void;
  setShowSaved: (saved: boolean) => void;
}

const ItemAttributeSection: React.FC<ItemAttributeSectionProps> = ({
  itemSystemId,
  categoryCode,
  existingEntries,
  setIsSaving,
  setShowSaved,
}) => {
  const [categoryAttributes, setCategoryAttributes] = useState<ItemAttribute[]>([]);
  const [customAttributes, setCustomAttributes] = useState<ItemAttribute[]>([]);
  const [entries, setEntries] = useState<ItemAttributeEntry[]>(existingEntries);
  const [attributeValuesMap, setAttributeValuesMap] = useState<Record<number, ItemAttributeValue[]>>({});
  
  // Load category attributes when category changes
  useEffect(() => {
    if (categoryCode) {
      loadCategoryAttributes(categoryCode);
    }
  }, [categoryCode]);
  
  // Load attribute values for option types
  useEffect(() => {
    const optionAttributes = [...categoryAttributes, ...customAttributes]
      .filter(attr => attr.type === 'option');
    optionAttributes.forEach(attr => {
      loadAttributeValues(attr.id);
    });
  }, [categoryAttributes, customAttributes]);
  
  const handleEntrySaved = (entry: ItemAttributeEntry) => {
    setEntries(prev => {
      const existing = prev.find(e => e.attribute === entry.attribute);
      if (existing) {
        return prev.map(e => e.attribute === entry.attribute ? entry : e);
      }
      return [...prev, entry];
    });
  };
  
  const handleAddCustomAttribute = () => {
    // Show modal to select attribute
    // Add to customAttributes
  };
  
  return (
    <Card title="Attributes">
      {/* Category Attributes */}
      {categoryAttributes.map(attr => (
        <ItemAttributeEntryField
          key={attr.id}
          attribute={attr}
          entry={entries.find(e => e.attribute === attr.id)}
          itemSystemId={itemSystemId}
          attributeValues={attributeValuesMap[attr.id] || []}
          setIsSaving={setIsSaving}
          setShowSaved={setShowSaved}
          onEntrySaved={handleEntrySaved}
        />
      ))}
      
      {/* Custom Attributes */}
      {customAttributes.map(attr => (
        <ItemAttributeEntryField
          key={attr.id}
          attribute={attr}
          entry={entries.find(e => e.attribute === attr.id)}
          itemSystemId={itemSystemId}
          attributeValues={attributeValuesMap[attr.id] || []}
          setIsSaving={setIsSaving}
          setShowSaved={setShowSaved}
          onEntrySaved={handleEntrySaved}
        />
      ))}
      
      <Button onClick={handleAddCustomAttribute}>
        + Add Custom Attribute
      </Button>
    </Card>
  );
};
```

### Step 6: Integration into Items.tsx

**Location**: `zentro-frontend/src/views/items/Items.tsx`

**Changes Needed**:

1. **Add to form values**:
   ```typescript
   const getInitialValues = (currentItem: Item | null): ItemFormValues => {
     return {
       // ... existing fields
       attribute_entries: currentItem?.attribute_entries || [],
     };
   };
   ```

2. **Transform API response**:
   ```typescript
   const transformApiToForm = (item: Item): ItemFormValues => {
     return {
       // ... existing fields
       attribute_entries: item.attribute_entries || [],
     };
   };
   ```

3. **Add ItemAttributeSection to form**:
   ```typescript
   <Form>
     {/* Existing fields */}
     
     {/* Add after category field or in a separate section */}
     {formik.values.system_id && (
       <ItemAttributeSection
         itemSystemId={formik.values.system_id}
         categoryCode={formik.values.item_category}
         existingEntries={formik.values.attribute_entries || []}
         setIsSaving={setIsSaving}
         setShowSaved={setShowSaved}
       />
     )}
   </Form>
   ```

4. **Load entries when item is loaded**:
   ```typescript
   useEffect(() => {
     if (currentItem?.system_id) {
       loadAttributeEntries(currentItem.system_id);
     }
   }, [currentItem?.system_id]);
   ```

## Implementation Details

### Auto-save Logic

**Pattern**: Same as existing AutoSaveField components

1. **On Blur**: Trigger save
2. **Check if item exists**: Must have `system_id`
3. **Build payload**: Based on attribute type
4. **Create or Update**: Use upsert endpoint
5. **Update state**: Call `onEntrySaved` callback
6. **Show feedback**: "Saving..." → "Saved" → Clear

### Handling Different Attribute Types

**Option Type**:
- Use MultiSelect component
- Store array of value IDs in `selected_values`
- Load values from `apiGetAttributeValues`

**Text Type**:
- Use Input component
- Store in `value_text`
- Simple string input

**Integer Type**:
- Use Input type="number"
- Store in `value_integer`
- Validate whole numbers only

**Decimal Type**:
- Use Input type="number" step="0.01"
- Store in `value_decimal`
- Allow decimal input

**Date Type**:
- Use Input type="date"
- Store in `value_date`
- Format: YYYY-MM-DD

### Category Attribute Auto-loading

**Trigger**: When `item_category` field changes

**Flow**:
1. User selects category in category field
2. Category field auto-saves (existing behavior)
3. ItemAttributeSection detects category change
4. Calls `apiGetCategoryAttributes(categoryCode)`
5. Displays attribute fields for each category attribute
6. If entries exist, pre-populate them

### Adding Custom Attributes

**Use Case**: Item needs an attribute not in its category

**Flow**:
1. User clicks "Add Custom Attribute"
2. Modal shows list of all attributes
3. User selects attribute
4. Attribute field appears in "Custom Attributes" section
5. User fills value and saves

### Entry Management

**One Entry Per Attribute**:
- Enforced by backend `unique_together = ("item", "attribute")`
- Frontend should prevent duplicate entries
- If entry exists, update it; if not, create it

**Deleting Entries**:
- Show delete button if entry exists
- Call `apiDeleteAttributeEntry(entry.id)`
- Remove from state

## State Management

### Redux Store (Optional)

If needed, add to `itemSlice.ts`:

```typescript
interface ItemState {
  // ... existing state
  attributeEntries: ItemAttributeEntry[];
  categoryAttributes: ItemAttribute[];
}

// Actions
setAttributeEntries: (entries: ItemAttributeEntry[]) => void;
addAttributeEntry: (entry: ItemAttributeEntry) => void;
updateAttributeEntry: (entry: ItemAttributeEntry) => void;
removeAttributeEntry: (entryId: number) => void;
setCategoryAttributes: (attributes: ItemAttribute[]) => void;
```

**Note**: May not be necessary if using local state in ItemAttributeSection

## Error Handling

**Pattern**: Same as existing AutoSaveField

1. **Network Errors**: Show toast notification
2. **Validation Errors**: Show field-level error
3. **Missing Item**: Don't save if item doesn't exist yet
4. **Missing Attribute**: Show error if attribute is deleted

## UI/UX Considerations

### Loading States
- Show spinner while loading category attributes
- Show "Saving..." indicator per field
- Show "Saved" checkmark briefly after save

### Empty States
- If no category selected: "Select a category to see attributes"
- If category has no attributes: "This category has no attributes"
- If no entries: Show empty fields ready for input

### Field Layout
- Group category attributes together
- Group custom attributes separately
- Use Card component for section
- Use FormItem for each field (consistent with existing)

### Validation
- Required fields: Mark with asterisk (if needed)
- Type validation: Enforce correct input type
- Backend validation: Show errors from API

## Testing Checklist

- [ ] Category attributes load when category is selected
- [ ] Attribute fields render correctly for each type
- [ ] Option type shows multi-select with correct values
- [ ] Text/Integer/Decimal/Date types show correct inputs
- [ ] Auto-save works on blur for each type
- [ ] New entries are created correctly
- [ ] Existing entries are updated correctly
- [ ] Entries are deleted correctly
- [ ] Custom attributes can be added
- [ ] Error handling works correctly
- [ ] Loading states display correctly
- [ ] Saved states display correctly

## File Structure

```
zentro-frontend/src/views/items/
├── Items.tsx (main form - add ItemAttributeSection)
├── components/
│   ├── ItemAttributeSection.tsx (NEW)
│   ├── ItemAttributeEntryField.tsx (NEW)
│   └── AddAttributeModal.tsx (NEW - for custom attributes)
├── @types/
│   └── index.d.ts (add attribute types)
└── store/
    └── itemSlice.ts (optional - add attribute actions)

zentro-frontend/src/services/
└── ItemService.ts (add attribute API functions)
```

## Implementation Order

1. **Backend APIs** (Step 1)
2. **TypeScript Types** (Step 2)
3. **API Service Functions** (Step 3)
4. **ItemAttributeEntryField Component** (Step 4)
5. **ItemAttributeSection Component** (Step 5)
6. **Integration into Items.tsx** (Step 6)
7. **Testing & Refinement**

## Notes

- **Keep it simple**: One entry = one attribute = one field
- **Follow patterns**: Use existing AutoSaveField as reference
- **Progressive enhancement**: Start with category attributes, add custom later
- **User experience**: Auto-load category attributes, make it seamless
- **Error handling**: Show clear errors, don't break the form

## Future Enhancements

- Bulk attribute assignment
- Attribute templates
- Attribute-based filtering in item list
- Attribute-based search
- Attribute validation rules
- Attribute dependencies (if X then show Y)

















































