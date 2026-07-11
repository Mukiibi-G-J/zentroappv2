# User Setup Implementation Summary

## What Was Implemented

A complete **User Setup Permission System** that allows administrators to control what individual users can see and do, specifically focusing on hiding buying prices and profit margins from certain users (like sales staff and cashiers).

## Files Modified/Created

### 1. **Models** (`authentication/models.py`)
- ✅ Created `UserSetup` model with 10 permission fields
- ✅ Added helper method `get_or_create_for_user()` for automatic setup creation
- ✅ Includes all CRUD permissions for pricing, sales, inventory, and reports

### 2. **Serializers** (`authentication/serializers.py`)
- ✅ Created `UserSetupSerializer` for API responses
- ✅ Updated `AuthTokenViewSerializer` to include user permissions in JWT token
- ✅ User permissions automatically embedded in authentication tokens

### 3. **Admin Interface** (`authentication/admin.py`)
- ✅ Created `UserSetupAdmin` with organized fieldsets
- ✅ Added list display with permission columns
- ✅ Implemented filtering and search capabilities
- ✅ Added readable user email display

### 4. **API Views** (`authentication/views.py`)
- ✅ Created `UserSetupViewSet` with full CRUD operations
- ✅ Custom actions:
  - `my-setup/` - Get current user's setup
  - `update-my-setup/` - Update own notes
  - `reset-to-defaults/` - Reset permissions to defaults
  - `users-without-setup/` - Find users without setup
  - `create-missing-setups/` - Bulk create setups

### 5. **URL Routes** (`authentication/urls.py`)
- ✅ Added `/api/user-setup/` routes
- ✅ Registered `UserSetupViewSet` with router

### 6. **Item Serializer** (`items/serializers.py`)
- ✅ Updated `ItemSerializer.to_representation()` to hide sensitive fields
- ✅ Automatically hides `unit_cost` and `last_direct_cost` if `can_see_buying_price = False`
- ✅ Automatically hides `markup_percentage` and `profit_percentage` if `can_see_profit_margin = False`

### 7. **Migrations**
- ✅ Created migration `authentication/migrations/0003_usersetup.py`
- ✅ Applied to all tenant schemas successfully

### 8. **Documentation**
- ✅ Created comprehensive `USER_SETUP_GUIDE.md`
- ✅ Created this implementation summary

### 9. **Management Commands**
- ✅ Created `setup_user_permissions` command for bulk operations
- ✅ Supports `--reset`, `--restrict-sales`, `--restrict-cashiers` flags

## How It Works

### 1. **Database Level**
Each user has a `UserSetup` record with boolean flags controlling access:
- `can_see_buying_price` - Controls visibility of cost prices
- `can_see_profit_margin` - Controls visibility of profit percentages
- Plus 8 other permission flags

### 2. **JWT Token Level**
When users log in, their permissions are embedded in the JWT token:
```json
{
  "user_permissions": {
    "canSeeBuyingPrice": false,
    "canSeeProfitMargin": false,
    ...
  }
}
```

### 3. **API Response Level**
The `ItemSerializer` automatically filters out restricted fields before sending to frontend:
- Restricted user sees: `itemName`, `unitPrice`, `inventory`
- Full access user sees: Above + `unitCost`, `markupPercentage`, `profitPercentage`

### 4. **Admin Interface Level**
Administrators can easily manage permissions through Django Admin with organized sections.

## Testing the Implementation

### 1. **Create a Test User**
```bash
# Access Django shell
python manage.py tenant_command shell --schema=<your-schema>

# Create a test user
from authentication.models import CustomUser, UserSetup

user = CustomUser.objects.create_user(
    email="testuser@example.com",
    username="testuser",
    full_name="Test User",
    phone_number="1234567890",
    password="testpass123"
)
```

### 2. **Setup Restricted Permissions**
```python
# In Django shell or admin panel
user_setup = UserSetup.get_or_create_for_user(user)
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.notes = "Test restricted user"
user_setup.save()
```

### 3. **Test API Response**
```bash
# Login as the restricted user
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"testuser@example.com","password":"testpass123"}'

# Check JWT token for user_permissions
# Then fetch items
curl -X GET http://localhost:8000/api/items/items/ \
  -H "Authorization: Bearer <token>"

# Verify that unit_cost and markup_percentage are NOT in response
```

### 4. **Test Admin Interface**
1. Go to http://localhost:8000/admin/
2. Navigate to Authentication > User Setups
3. Create/Edit user setups
4. Verify permissions are saved correctly

### 5. **Use Management Command**
```bash
# Create setups for all users
python manage.py tenant_command setup_user_permissions --schema=<your-schema>

# Reset all to defaults
python manage.py tenant_command setup_user_permissions --schema=<your-schema> --reset

# Apply sales staff restrictions
python manage.py tenant_command setup_user_permissions --schema=<your-schema> --reset --restrict-sales

# Apply cashier restrictions
python manage.py tenant_command setup_user_permissions --schema=<your-schema> --reset --restrict-cashiers
```

## API Endpoints Available

### Public Access (with authentication)
- `GET /api/user-setup/` - List all user setups
- `GET /api/user-setup/{id}/` - Get specific setup
- `GET /api/user-setup/my-setup/` - Get own setup
- `POST /api/user-setup/` - Create new setup (admin)
- `PUT/PATCH /api/user-setup/{id}/` - Update setup (admin)
- `DELETE /api/user-setup/{id}/` - Delete setup (admin)

### Custom Actions
- `GET /api/user-setup/users-without-setup/` - List users without setup
- `POST /api/user-setup/create-missing-setups/` - Create setups for all users
- `POST /api/user-setup/{id}/reset-to-defaults/` - Reset to default permissions
- `PATCH /api/user-setup/update-my-setup/` - Update own notes

## Common Use Cases

### Scenario 1: Hide Prices from Sales Staff
```python
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.can_see_item_cost = False
user_setup.notes = "Sales staff - no cost visibility"
user_setup.save()
```

### Scenario 2: Cashier with Minimal Access
```python
user_setup.can_see_buying_price = False
user_setup.can_see_profit_margin = False
user_setup.can_see_customer_balance = False
user_setup.can_see_financial_reports = False
user_setup.can_export_data = False
user_setup.notes = "Cashier - POS only"
user_setup.save()
```

### Scenario 3: Manager with Full Access
```python
user_setup.can_see_buying_price = True
user_setup.can_see_profit_margin = True
user_setup.can_edit_buying_price = True
user_setup.can_adjust_inventory = True
user_setup.notes = "Manager - full access"
user_setup.save()
```

## Frontend Integration (To Do)

### 1. **TypeScript Types** (to be created)
```typescript
// src/types/userSetup.ts
export interface UserPermissions {
  canSeeBuyingPrice: boolean;
  canSeeProfitMargin: boolean;
  canSeeItemCost: boolean;
  canEditBuyingPrice: boolean;
  canSeeSalesHistory: boolean;
  canSeeCustomerBalance: boolean;
  canSeeStockValue: boolean;
  canAdjustInventory: boolean;
  canSeeFinancialReports: boolean;
  canExportData: boolean;
}
```

### 2. **Redux Store** (to be updated)
```typescript
// Add to user state
interface UserState {
  // ... existing fields
  userPermissions?: UserPermissions;
}
```

### 3. **Components** (to be created/updated)
```typescript
// Conditional rendering in item cards
{userPermissions?.canSeeBuyingPrice && (
  <div>Cost: {item.unitCost}</div>
)}

{userPermissions?.canSeeProfitMargin && (
  <div>Profit: {item.profitPercentage}%</div>
)}
```

### 4. **API Service** (to be created)
```typescript
// src/services/UserSetupService.ts
export const getUserSetup = () => 
  ApiService.fetchData({ url: '/user-setup/my-setup/', method: 'get' });

export const updateUserSetup = (id: number, data: Partial<UserSetup>) =>
  ApiService.fetchData({ url: `/user-setup/${id}/`, method: 'patch', data });
```

## Security Notes

1. ✅ Permissions are checked at the serializer level (backend)
2. ✅ JWT token includes permissions (eliminates extra DB queries)
3. ✅ Automatic setup creation with secure defaults
4. ✅ Users can only update their own notes
5. ✅ Only admins can modify permission flags
6. ✅ Audit trail with created_at and updated_at timestamps

## Next Steps

1. **Test thoroughly** with different user roles
2. **Implement frontend** components to respect permissions
3. **Add to other serializers** (e.g., PurchaseSerializer, SalesSerializer)
4. **Create user documentation** for end users
5. **Add permission checks** to other views as needed

## Maintenance

### To Add New Permissions:
1. Add boolean field to `UserSetup` model
2. Update `get_or_create_for_user()` defaults
3. Add to JWT token in serializer
4. Update admin fieldsets
5. Create migration
6. Update documentation

### To Apply to Other Models:
1. Update the model's serializer `to_representation()` method
2. Import `UserSetup` model
3. Check user permissions and filter fields accordingly

## Support

For questions or issues:
1. Check `USER_SETUP_GUIDE.md` for detailed documentation
2. Review test cases in this document
3. Contact the development team

---

**Implementation Date**: December 2024
**Status**: ✅ Complete and Ready for Testing
**Migration Status**: ✅ Applied to All Tenant Schemas

