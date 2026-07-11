# User Setup Permission System

## Overview

The User Setup system provides fine-grained control over what individual users can see and do in the ZentroApp system. This is separate from role-based permissions and allows administrators to customize each user's access to sensitive financial information.

## Features

### Pricing & Profit Permissions
- **Can See Buying Price**: Controls visibility of cost prices and last direct cost on items
- **Can See Profit Margin**: Controls visibility of profit percentage and markup percentage
- **Can See Item Cost**: Controls visibility of item cost in transactions
- **Can Edit Buying Price**: Controls ability to modify cost prices

### Sales Permissions
- **Can See Sales History**: Controls access to historical sales data
- **Can See Customer Balance**: Controls visibility of customer outstanding balances

### Inventory Permissions
- **Can See Stock Value**: Controls visibility of total inventory value
- **Can Adjust Inventory**: Controls ability to make inventory adjustments

### Reports & Data
- **Can See Financial Reports**: Controls access to financial reports and analytics
- **Can Export Data**: Controls ability to export data to Excel/PDF

## Database Model

### Location
`zentro-backend/authentication/models.py`

### Model: `UserSetup`
```python
class UserSetup(BaseModel):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    
    # Pricing & Profit Permissions
    can_see_buying_price = models.BooleanField(default=True)
    can_see_profit_margin = models.BooleanField(default=True)
    can_see_item_cost = models.BooleanField(default=True)
    can_edit_buying_price = models.BooleanField(default=False)
    
    # Sales Permissions
    can_see_sales_history = models.BooleanField(default=True)
    can_see_customer_balance = models.BooleanField(default=True)
    
    # Inventory Permissions
    can_see_stock_value = models.BooleanField(default=True)
    can_adjust_inventory = models.BooleanField(default=False)
    
    # Reports Permissions
    can_see_financial_reports = models.BooleanField(default=True)
    can_export_data = models.BooleanField(default=True)
    
    notes = models.TextField(blank=True)
```

## JWT Token Integration

User permissions are automatically included in JWT tokens:

```json
{
  "user_permissions": {
    "canSeeBuyingPrice": true,
    "canSeeProfitMargin": false,
    "canSeeItemCost": true,
    "canEditBuyingPrice": false,
    "canSeeSalesHistory": true,
    "canSeeCustomerBalance": true,
    "canSeeStockValue": true,
    "canAdjustInventory": false,
    "canSeeFinancialReports": true,
    "canExportData": true
  }
}
```

## API Endpoints

### Base URL
`/api/user-setup/`

### Available Endpoints

#### 1. List All User Setups
```http
GET /api/user-setup/
```
Returns list of all user setups with pagination, search, and filtering.

**Query Parameters:**
- `search`: Search by username, email, full name, or notes
- `ordering`: Sort by username, created_at, or updated_at

**Response:**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": 5,
      "userId": 5,
      "username": "john.doe",
      "email": "john@example.com",
      "fullName": "John Doe",
      "canSeeBuyingPrice": false,
      "canSeeProfitMargin": false,
      "canSeeItemCost": true,
      "canEditBuyingPrice": false,
      "canSeeSalesHistory": true,
      "canSeeCustomerBalance": true,
      "canSeeStockValue": false,
      "canAdjustInventory": false,
      "canSeeFinancialReports": false,
      "canExportData": true,
      "notes": "Sales staff - restricted financial access",
      "createdAt": "2024-01-01T10:00:00Z",
      "updatedAt": "2024-01-15T14:30:00Z"
    }
  ]
}
```

#### 2. Get Specific User Setup
```http
GET /api/user-setup/{id}/
```
Returns details of a specific user setup.

#### 3. Get Current User's Setup
```http
GET /api/user-setup/my-setup/
```
Returns the logged-in user's setup.

**Response:**
```json
{
  "id": 1,
  "user": 5,
  "userId": 5,
  "username": "john.doe",
  "email": "john@example.com",
  "fullName": "John Doe",
  "canSeeBuyingPrice": true,
  "canSeeProfitMargin": true,
  "canSeeItemCost": true,
  "canEditBuyingPrice": false,
  ...
}
```

#### 4. Create User Setup
```http
POST /api/user-setup/
Content-Type: application/json

{
  "user": 5,
  "canSeeBuyingPrice": false,
  "canSeeProfitMargin": false,
  "notes": "Sales staff - restricted access"
}
```

#### 5. Update User Setup
```http
PUT /api/user-setup/{id}/
PATCH /api/user-setup/{id}/
Content-Type: application/json

{
  "canSeeBuyingPrice": true,
  "canSeeProfitMargin": false
}
```

#### 6. Update Current User's Setup (Limited)
```http
PATCH /api/user-setup/update-my-setup/
Content-Type: application/json

{
  "notes": "Updated my preferences"
}
```
Note: Users can only update their own notes field.

#### 7. Reset to Defaults
```http
POST /api/user-setup/{id}/reset-to-defaults/
```
Resets all permissions to default values.

**Response:**
```json
{
  "message": "User setup reset to defaults successfully",
  "data": { ... }
}
```

#### 8. Get Users Without Setup
```http
GET /api/user-setup/users-without-setup/
```
Returns list of users who don't have a setup yet.

**Response:**
```json
[
  {
    "id": 10,
    "username": "jane.smith",
    "email": "jane@example.com",
    "fullName": "Jane Smith"
  }
]
```

#### 9. Create Missing Setups
```http
POST /api/user-setup/create-missing-setups/
```
Creates user setups for all users who don't have one.

**Response:**
```json
{
  "message": "Created 5 user setup(s) successfully",
  "createdCount": 5
}
```

## Item Serializer Integration

The `ItemSerializer` automatically hides sensitive fields based on user permissions:

### Hidden Fields Based on Permissions

1. **When `canSeeBuyingPrice = false`:**
   - `unit_cost` field is removed
   - `last_direct_cost` field is removed

2. **When `canSeeProfitMargin = false`:**
   - `markup_percentage` field is removed
   - `profit_percentage` field is removed

### Example Item Response (Restricted User)

**User with restricted permissions:**
```json
{
  "itemId": 1,
  "itemName": "Product A",
  "unitPrice": 5000,
  "inventory": 100
  // unit_cost is hidden
  // markup_percentage is hidden
  // profit_percentage is hidden
}
```

**User with full permissions:**
```json
{
  "itemId": 1,
  "itemName": "Product A",
  "unitPrice": 5000,
  "unitCost": 3000,
  "markupPercentage": 66.67,
  "profitPercentage": 40.0,
  "inventory": 100
}
```

## Admin Interface

### Location
Django Admin: `/admin/authentication/usersetup/`

### Features
- List view with filtering by permissions
- Search by username, email, full name, notes
- Organized fieldsets for easy management:
  - User Information
  - Pricing & Profit Permissions
  - Sales Permissions
  - Inventory Permissions
  - Reports & Data Export
  - Additional Notes

### Bulk Actions
Admins can select multiple users and update their permissions in bulk.

## Usage Examples

### Python Code Examples

#### 1. Get or Create User Setup
```python
from authentication.models import UserSetup, CustomUser

user = CustomUser.objects.get(email="john@example.com")
user_setup = UserSetup.get_or_create_for_user(user)
```

#### 2. Check User Permissions
```python
# In a view or serializer
user_setup = UserSetup.objects.get(user=request.user)

if user_setup.can_see_buying_price:
    # Include cost information
    data['unitCost'] = item.unit_cost
else:
    # Hide cost information
    pass
```

#### 3. Update User Permissions
```python
user_setup = UserSetup.objects.get(user=user)
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.notes = "Sales staff - restricted financial access"
user_setup.save()
```

### Frontend Usage (TypeScript/React)

#### 1. Access Permissions from Token
```typescript
import { useAppSelector } from '@/store';

const MyComponent = () => {
  const userPermissions = useAppSelector((state) => state.auth.user?.userPermissions);

  if (userPermissions?.canSeeBuyingPrice) {
    // Show buying price
  }
};
```

#### 2. Conditional Rendering
```typescript
{userPermissions?.canSeeProfitMargin && (
  <div>
    <label>Profit Margin:</label>
    <span>{item.profitPercentage}%</span>
  </div>
)}
```

#### 3. API Service Example
```typescript
import ApiService from '@/services/ApiService';

// Get current user's setup
const getUserSetup = async () => {
  const response = await ApiService.fetchData({
    url: '/user-setup/my-setup/',
    method: 'get',
  });
  return response.data;
};

// Update user setup
const updateUserSetup = async (id: number, data: Partial<UserSetup>) => {
  const response = await ApiService.fetchData({
    url: `/user-setup/${id}/`,
    method: 'patch',
    data,
  });
  return response.data;
};
```

## Default Permissions

When a user setup is created (automatically or manually), the following defaults are applied:

```python
can_see_buying_price = True
can_see_profit_margin = True
can_see_item_cost = True
can_edit_buying_price = False  # Restricted by default
can_see_sales_history = True
can_see_customer_balance = True
can_see_stock_value = True
can_adjust_inventory = False  # Restricted by default
can_see_financial_reports = True
can_export_data = True
```

## Security Considerations

1. **Automatic Setup Creation**: User setups are created automatically with default permissions when first accessed
2. **JWT Integration**: Permissions are embedded in JWT tokens, eliminating extra database queries
3. **Serializer-Level Filtering**: Sensitive data is removed at the serializer level, ensuring it never reaches the frontend
4. **Admin-Only Updates**: Only administrators can modify other users' permission settings
5. **Self-Service Notes**: Users can only update their own notes field

## Best Practices

1. **Review Regularly**: Periodically review user setups to ensure appropriate access levels
2. **Document Restrictions**: Use the notes field to document why specific restrictions are in place
3. **Least Privilege**: Start with minimal permissions and grant additional access as needed
4. **Audit Trail**: All setup changes are tracked with created_at and updated_at timestamps
5. **Test Thoroughly**: Test user experience with restricted permissions before deploying

## Common Use Cases

### 1. Sales Staff
```python
# Hide cost and profit information from sales team
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.can_see_item_cost = False
user_setup.can_see_stock_value = False
user_setup.notes = "Sales staff - no cost visibility"
```

### 2. Inventory Clerk
```python
# Allow inventory management but hide financial reports
user_setup.can_adjust_inventory = True
user_setup.can_see_financial_reports = False
user_setup.notes = "Inventory clerk - operational access only"
```

### 3. Cashier
```python
# Minimal permissions for POS operations
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.can_see_customer_balance = False
user_setup.can_see_financial_reports = False
user_setup.can_export_data = False
user_setup.notes = "Cashier - POS access only"
```

### 4. Manager
```python
# Full access to all information
user_setup.can_see_buying_price = True
user_setup.can_see_profit_margin = True
user_setup.can_edit_buying_price = True
user_setup.can_adjust_inventory = True
user_setup.can_see_financial_reports = True
user_setup.notes = "Manager - full access"
```

## Troubleshooting

### Issue: User can still see restricted fields
**Solution**: Ensure the user logs out and logs back in to get a new JWT token with updated permissions.

### Issue: UserSetup doesn't exist for user
**Solution**: The system automatically creates setups with default permissions. If needed, manually trigger:
```python
UserSetup.get_or_create_for_user(user)
```

### Issue: Permissions not working in API
**Solution**: Ensure the request context is passed to the serializer:
```python
serializer = ItemSerializer(items, many=True, context={'request': request})
```

## Related Documentation

- [Permission System Guide](PERMISSIONS_SYSTEM_GUIDE.md)
- [Custom User Model](authentication/models.py)
- [JWT Token Structure](authentication/serializers.py)
- [Item API](items/views.py)

## Support

For issues or questions about the User Setup system, contact the development team or create an issue in the project repository.

