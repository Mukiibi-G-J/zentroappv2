# Item Attributes System Documentation

## Overview

The Item Attributes system allows you to define custom attributes for items (similar to Business Central). Attributes can be assigned at the **category level** (as templates) or directly on **individual items**. This provides flexibility while maintaining consistency across similar products.

## Architecture

### System Flow Diagram

```
ItemAttribute ──< allows >── ItemAttributeValue
      │                           (Red, Blue, S, M, L...)
      │
      └──< used by >── ItemCategory
                       (e.g. Apparel, Electronics)
                              │
                              │ (Category defaults load these attributes)
                              ▼
                            Item
                              │
                              │ (Actual values stored per item)
                              ▼
                      ItemAttributeEntry
                        ├─ attribute → Color
                        ├─ selected_values → Red, Blue (for option type)
                        ├─ value_text (for text type)
                        ├─ value_integer (for integer type)
                        ├─ value_decimal (for decimal type)
                        └─ value_date (for date type)
```

## Database Models

### 1. ItemAttribute

**Purpose**: Defines the attribute definition (what attributes exist in the system)

**Fields**:
- `name` (CharField) - Attribute name (e.g., "Color", "Size")
- `type` (CharField/ChoiceField) - Attribute type:
  - `option` - Multi-select from predefined values
  - `text` - Free text input
  - `integer` - Whole number
  - `decimal` - Decimal number
  - `date` - Date picker
- `blocked` (BooleanField) - True = Blocked, False = Active
- `values` (ManyToManyField) - Links to ItemAttributeValue (for option type)

**Example**:
```python
ItemAttribute(
    name="Color",
    type="option",
    blocked=False,
    values=[Red, Blue, Black, White]  # ItemAttributeValue instances
)
```

### 2. ItemAttributeValue

**Purpose**: Stores predefined values for option-type attributes

**Fields**:
- `value` (CharField) - The actual value (e.g., "Red", "S", "XL")
- `blocked` (BooleanField) - True = Blocked, False = Active

**Example**:
```python
ItemAttributeValue(value="Red", blocked=False)
ItemAttributeValue(value="Blue", blocked=False)
ItemAttributeValue(value="M", blocked=False)
```

### 3. ItemCategory (Extended)

**New Field**:
- `attributes` (ManyToManyField to ItemAttribute) - Attributes assigned to this category

**Purpose**: Categories act as templates. When you assign attributes to a category, items in that category will have those attributes available.

**Example**:
```python
ItemCategory(
    code="TSHIRT",
    description="T-Shirts",
    attributes=[Color, Size, Material]  # ItemAttribute instances
)
```

### 4. ItemAttributeEntry

**Purpose**: Stores the actual attribute values for a specific item

**Fields**:
- `item` (ForeignKey to Item) - The item this entry belongs to
- `attribute` (ForeignKey to ItemAttribute) - Which attribute this entry is for
- `selected_values` (ManyToManyField to ItemAttributeValue) - For option type
- `value_text` (CharField) - For text type
- `value_integer` (IntegerField) - For integer type
- `value_decimal` (DecimalField) - For decimal type
- `value_date` (DateField) - For date type

**Constraints**:
- `unique_together = ("item", "attribute")` - One entry per attribute per item

**Example**:
```python
# For option type (Color)
ItemAttributeEntry(
    item=nike_shirt,
    attribute=color_attribute,
    selected_values=[red_value, blue_value]
)

# For text type (Material)
ItemAttributeEntry(
    item=nike_shirt,
    attribute=material_attribute,
    value_text="100% Cotton"
)

# For date type (Release Date)
ItemAttributeEntry(
    item=nike_shirt,
    attribute=release_date_attribute,
    value_date=date(2024, 1, 15)
)
```

## Attribute Types Explained

### 1. Option Type
- **Use Case**: When you have a fixed list of choices
- **Example**: Color (Red, Blue, Black), Size (S, M, L, XL)
- **Storage**: Uses `selected_values` ManyToManyField
- **UI**: Multi-select dropdown/checkboxes
- **Requires**: ItemAttributeValue entries must be created first

### 2. Text Type
- **Use Case**: Free-form text input
- **Example**: Material description, Notes, Brand
- **Storage**: Uses `value_text` CharField
- **UI**: Text input field
- **Requires**: No predefined values needed

### 3. Integer Type
- **Use Case**: Whole numbers
- **Example**: Warranty months, Quantity per pack
- **Storage**: Uses `value_integer` IntegerField
- **UI**: Number input (integers only)
- **Requires**: No predefined values needed

### 4. Decimal Type
- **Use Case**: Decimal numbers
- **Example**: Weight (kg), Dimensions (cm)
- **Storage**: Uses `value_decimal` DecimalField
- **UI**: Decimal number input
- **Requires**: No predefined values needed

### 5. Date Type
- **Use Case**: Dates
- **Example**: Release date, Expiry date, Launch date
- **Storage**: Uses `value_date` DateField
- **UI**: Date picker
- **Requires**: No predefined values needed

## Workflow: How to Use the System

### Step 1: Create Attribute Values (For Option Types)

1. Go to **Items → Item Attribute Values**
2. Create values that will be used in option-type attributes:
   - Red, Blue, Black, White (for Color)
   - S, M, L, XL (for Size)
   - etc.

### Step 2: Create Attributes

1. Go to **Items → Item Attributes**
2. Create each attribute:
   - **Name**: Color
   - **Type**: option
   - **Values**: Select Red, Blue, Black, White (using filter_horizontal)
3. Repeat for other attributes

### Step 3: Assign Attributes to Categories (Optional but Recommended)

1. Go to **Items → Item Categories**
2. Edit a category (e.g., "T-Shirts")
3. In the **Attributes** field, select the attributes this category should have
4. Save

**Why?** This acts as a template. When you create an item in this category, these attributes will be suggested/available.

### Step 4: Create Items with Attributes

1. Go to **Items → Items**
2. Create or edit an item
3. Set the **Item Category** (if you assigned attributes to the category, they'll be available)
4. Scroll to **Item Attribute Entries** inline section
5. Add entries for each attribute:
   - For **option type**: Select values from the multi-select
   - For **text type**: Enter text in Value Text field
   - For **integer type**: Enter number in Value Integer field
   - For **decimal type**: Enter decimal in Value Decimal field
   - For **date type**: Select date in Value Date field
6. Save

## Example: Complete Setup

### Scenario: Clothing Store

#### 1. Create Attribute Values
```
- Red
- Blue
- Black
- White
- S
- M
- L
- XL
```

#### 2. Create Attributes
```
Attribute: Color
- Type: option
- Values: Red, Blue, Black, White

Attribute: Size
- Type: option
- Values: S, M, L, XL

Attribute: Material
- Type: text
- Values: (none needed)

Attribute: Release Date
- Type: date
- Values: (none needed)
```

#### 3. Assign to Category
```
Category: T-Shirts
- Attributes: Color, Size, Material, Release Date
```

#### 4. Create Item
```
Item: Nike Air Max T-Shirt
- Category: T-Shirts

Attribute Entries:
1. Color → Selected Values: Red, Blue
2. Size → Selected Values: M, L, XL
3. Material → Value Text: "100% Cotton"
4. Release Date → Value Date: 2024-01-15
```

## Django Admin Configuration

### ItemAttributeAdmin
- **List Display**: name, type, blocked
- **Filters**: type, blocked
- **Search**: name
- **Filter Horizontal**: values (for selecting ItemAttributeValues)

### ItemAttributeValueAdmin
- **List Display**: value, blocked
- **Filters**: blocked
- **Search**: value

### ItemAttributeEntryAdmin
- **List Display**: item, attribute, display_value
- **Search**: item__item_name, attribute__name
- **Autocomplete**: item, attribute
- **Filter Horizontal**: selected_values

### ItemCategoryAdmin
- **Filter Horizontal**: attributes (for selecting ItemAttributes)
- **Fieldset**: Includes attributes field

### ItemAdmin
- **Inline**: ItemAttributeEntryInline
  - Shows attribute entries directly on item edit page
  - Uses StackedInline layout
  - Has filter_horizontal for selected_values
  - Has autocomplete for attribute field

## Model Methods & Properties

### ItemAttributeEntry.display_value
**Purpose**: Returns a formatted string representation of the attribute value

**Logic**:
- **Option type**: Returns comma-separated list of selected values
- **Text type**: Returns value_text
- **Integer type**: Returns string of value_integer
- **Decimal type**: Returns string of value_decimal
- **Date type**: Returns formatted date string (YYYY-MM-DD)

**Example**:
```python
entry = ItemAttributeEntry.objects.get(...)
print(entry.display_value)  # "Red, Blue" or "100% Cotton" or "2024-01-15"
```

### ItemAttributeEntry.clean()
**Purpose**: Validates that the correct value field is used based on attribute type

**Validation Rules**:
- Option type: Must have selected_values, other fields should be empty
- Text type: Must have value_text, other fields should be empty
- Integer type: Must have value_integer, other fields should be empty
- Decimal type: Must have value_decimal, other fields should be empty
- Date type: Must have value_date, other fields should be empty

## Database Relationships

```
ItemAttribute (1) ──< (M) ItemAttributeValue
     │
     │ (M2M)
     │
     └──< (M) ItemCategory.attributes

ItemAttribute (1) ──< (M) ItemAttributeEntry
     │
     │ (FK)
     │
Item (1) ──< (M) ItemAttributeEntry
     │
     │ (FK)
     │
ItemCategory (1) ──< (M) Item
```

## Best Practices

### 1. Category-Based Attributes
- **Recommended**: Assign common attributes to categories
- **Benefit**: Consistency across similar items
- **Example**: All "T-Shirts" have Color and Size

### 2. Attribute Naming
- Use clear, descriptive names
- Examples: "Color", "Size", "Material" (good)
- Avoid: "Attr1", "Field2" (bad)

### 3. Option Values
- Keep option values concise
- Use consistent capitalization
- Examples: "Red", "Blue" (good) vs "red", "RED", "Red Color" (inconsistent)

### 4. Item-Specific Attributes
- You can add attributes directly to items even if not in category
- Use for special cases or one-off attributes
- Example: A specific item might need a "Special Edition" attribute

### 5. Blocked Attributes/Values
- Use `blocked=True` to hide from new entries
- Don't delete - keeps historical data intact
- Example: Discontinue "XXL" size but keep for existing items

## Querying Examples

### Get all attributes for an item
```python
item = Item.objects.get(no="ITEM001")
attributes = ItemAttributeEntry.objects.filter(item=item)
for entry in attributes:
    print(f"{entry.attribute.name}: {entry.display_value}")
```

### Get items with specific attribute value
```python
# Find all items with Color = Red
red_value = ItemAttributeValue.objects.get(value="Red")
color_attr = ItemAttribute.objects.get(name="Color")
red_items = Item.objects.filter(
    attribute_entries__attribute=color_attr,
    attribute_entries__selected_values=red_value
).distinct()
```

### Get category attributes
```python
category = ItemCategory.objects.get(code="TSHIRT")
attributes = category.attributes.all()
# Returns: [Color, Size, Material, Release Date]
```

## Migration History

- **0005**: Created ItemAttribute and ItemAttributeValue models
- **0006**: Added ItemCategory.attributes M2M field and ItemAttributeEntry model

## Future Enhancements (Frontend)

1. **Auto-load category attributes** when item category is selected
2. **Dynamic form fields** based on attribute type
3. **Validation** to ensure correct value type is entered
4. **Bulk attribute assignment** for multiple items
5. **Attribute filtering** in item lists
6. **Attribute-based search** functionality

## Related Files

- **Models**: `zentro-backend/items/models.py`
- **Admin**: `zentro-backend/items/admin.py`
- **Migrations**: `zentro-backend/items/migrations/`

## Support

For questions or issues with the Item Attributes system, refer to this documentation or contact the development team.

















































