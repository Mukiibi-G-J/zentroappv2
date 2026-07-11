# ZentroApp - User Management System Deployment Guide

## 📋 Overview

This guide covers the deployment of the new **User Management System** and related features to production.

### 🚀 Features Included

1. **User Management Module**

   - User Management (CRUD operations for users)
   - User Group Management (manage groups and assign users)
   - Permission Set Management (configure page-level permissions)
   - Role Management (assign role centers to roles)
   - Role Center Management (configure module visibility)

2. **Purchase & Payment History**

   - Purchase History page added to Purchases module
   - Payment History page added to Payments module

3. **Auto-Generated Codes**

   - User Groups automatically generate codes from names
   - Role Centers automatically generate codes from names

4. **Enhanced Permission System**
   - Updated permission sets include new pages
   - Complete CRUD control for all pages

---

## 📦 What's New

### Backend Changes

#### New Models & Serializers

- `UserManagementViewSet` - Complete user CRUD
- `UserGroupViewSet` - Group management with member operations
- `PermissionSetViewSet` - Permission set builder
- `RoleViewSet` - Role and role center management
- `RoleCenterViewSet` - Module visibility configuration

#### New Page Objects (IDs)

- **10801** - User Management
- **10802** - User Group Management
- **10803** - Permission Set Management
- **10804** - User Roles Management
- **10805** - Role Center Management
- **10302** - Purchase History
- **10402** - Payment History

#### New Permission Sets

- **USER_MGMT_FULL** - Full user management access
- **USER_MGMT_BASIC** - Basic user management (no delete)
- **USER_MGMT_VIEW_ONLY** - Read-only user management

#### Updated Permission Sets

- **PURCHASES_FULL** - Now includes Purchase History
- **PAYMENTS_FULL** - Now includes Payment History

### Frontend Changes

#### New Routes

- `/app/user-management/users`
- `/app/user-management/user-groups`
- `/app/user-management/permission-sets`
- `/app/user-management/roles`
- `/app/user-management/role-centers`
- `/app/purchases/purchases-history`
- `/app/payments/payment-history`

#### New Navigation Items

- User Management module in sidebar (when user has access)
- Purchase History under Purchases
- Payment History under Payments

#### New Services & Redux Slices

- `UserManagementService`
- `UserGroupService`
- `PermissionSetService`
- `RoleManagementService`
- Redux slices for all user management state

---

## 🔧 Deployment Instructions

### Method 1: Automated Script (Recommended)

#### For Linux/Mac Production:

```bash
# Make script executable
chmod +x deploy_user_management.sh

# Run deployment
./deploy_user_management.sh <tenant_schema>

# Example:
./deploy_user_management.sh ekk
```

#### For Windows/Local:

```powershell
# Run deployment
.\deploy_user_management.ps1 -Schema <tenant_schema>

# Example:
.\deploy_user_management.ps1 -Schema ekk
```

### Method 2: Manual Deployment

If you prefer to run commands manually:

#### Step 1: Activate Environment

```bash
# Linux/Mac
source env/bin/activate

# Windows
.\env\Scripts\activate
```

#### Step 2: Run Migrations

```bash
python manage.py migrate_schemas
```

#### Step 3: Populate Page Objects

```bash
# Replace 'ekk' with your tenant schema
python manage.py tenant_command populate_page_objects --schema=hardwareworld
```

This creates/updates:

- User Management pages (10801-10805)
- Purchase History (10302)
- Payment History (10402)
- All other existing pages

#### Step 4: Setup Permission Sets

```bash
# Replace 'ekk' with your tenant schema
python manage.py tenant_command setup_page_permissions --schema=hardwareworld
```

This creates/updates:

- All permission sets including USER*MGMT*\*
- Updates PURCHASES_FULL and PAYMENTS_FULL

#### Step 5: Collect Static Files (Production Only)

```bash
python manage.py collectstatic --noinput
```

#### Step 6: Restart Application

```bash
# If using systemd
sudo systemctl restart zentroapp

# If using Docker
docker-compose restart

# If using gunicorn
pkill gunicorn && gunicorn config.wsgi:application
```

---

## ⚙️ Post-Deployment Configuration

### 1. Django Admin Setup

Log into Django Admin: `http://your-domain/admin/`

#### A. Update Role Centers

1. Navigate to **Authentication → Role Centers**
2. Edit **Admin Center** (or create it if it doesn't exist)
3. Ensure `modules` includes:
   ```json
   [
     "sales",
     "customers",
     "items",
     "purchases",
     "suppliers",
     "payments",
     "financials",
     "expenses",
     "user_management"
   ]
   ```

#### B. Assign Permission Sets to User Groups

1. Navigate to **Authentication → User Groups**
2. Edit **Admin** group (or your main admin group)
3. Add permission sets:
   - USER_MGMT_FULL
   - PURCHASES_FULL (should already be there)
   - PAYMENTS_FULL (should already be there)
   - Any other needed permission sets

#### C. Verify Default Role

1. Ensure the **Admin** user group has a **Default Profile (Role)**
2. That role should link to the **Admin Center** role center

### 2. Frontend Deployment

#### Build Frontend

```bash
cd zentro-frontend

# Install dependencies (if new)
npm install

# Build for production
npm run build

# Deploy dist folder to your hosting
```

#### Environment Variables

Ensure your production `.env` has:

```env
VITE_API_BASE_URL=https://your-api-domain.com
```

### 3. User Token Refresh

**⚠️ CRITICAL**: All existing users must **log out and log back in** to receive updated JWT tokens with the new page permissions.

You can notify users via:

- Email
- In-app notification
- Dashboard banner

---

## ✅ Testing Checklist

After deployment, test the following:

### Backend Tests

- [ ] Admin can access `/admin/authentication/usergroup/`
- [ ] Admin can access `/admin/authentication/role/`
- [ ] Admin can access `/admin/authentication/rolecenter/`
- [ ] API endpoint works: `GET /api/users/`
- [ ] API endpoint works: `GET /api/user-groups/`
- [ ] API endpoint works: `GET /api/permission-sets/`
- [ ] API endpoint works: `GET /api/roles/`
- [ ] API endpoint works: `GET /api/role-centers/`

### Frontend Tests

- [ ] Login as admin
- [ ] User Management module appears in sidebar
- [ ] Can navigate to Users page
- [ ] Can navigate to User Groups page
- [ ] Can navigate to Permission Sets page
- [ ] Can navigate to Roles page
- [ ] Can navigate to Role Centers page
- [ ] Purchase History appears under Purchases
- [ ] Payment History appears under Payments
- [ ] Can create a new user
- [ ] Can create a new user group
- [ ] Can create a new permission set
- [ ] Can create a new role
- [ ] Can create a new role center
- [ ] Auto-save fields work correctly
- [ ] User group member assignment works
- [ ] Permission set assignment to groups works

### Permission Tests

- [ ] Create a test user with limited permissions
- [ ] Assign them to a group with USER_MGMT_VIEW_ONLY
- [ ] Login as that user
- [ ] Verify they can view but not edit User Management
- [ ] Test other permission levels

---

## 🐛 Troubleshooting

### Issue: "User Management" not showing in sidebar

**Solution:**

1. Check role center includes `"user_management"` module
2. Check user group has appropriate permission sets
3. User must log out and log back in for new JWT token
4. Clear browser cache

### Issue: "Purchase/Payment History" not showing

**Solution:**

1. Check page objects were created (IDs 10302, 10402)
2. Check permission sets include these pages
3. User must log out and log back in
4. Check navigation config was deployed

### Issue: "Code field is required" when creating Role Center/User Group

**Solution:**

- Ensure you deployed the updated serializers with auto-code generation
- Check `authentication/user_management_serializers.py` has the updated code
- Restart Django application

### Issue: Permission denied errors

**Solution:**

1. Check user is assigned to correct user group
2. Check user group has necessary permission sets
3. Verify permission set has the required page permissions
4. User must refresh JWT token (log out/in)

### Issue: Database migration errors

**Solution:**

```bash
# Check migration status
python manage.py showmigrations

# If needed, fake migrations (BE CAREFUL)
python manage.py migrate --fake authentication <migration_number>

# Re-run populate commands
python manage.py tenant_command populate_page_objects --schema=<schema>
python manage.py tenant_command setup_page_permissions --schema=<schema>
```

---

## 📊 Database Changes

### New Tables

None (uses existing Django models)

### Modified Tables

- `authentication_customuser` - No schema changes
- `authentication_usergroup` - No schema changes
- `authentication_role` - No schema changes
- `authentication_rolecenter` - No schema changes
- `permissions_permissionset` - No schema changes
- `permissions_permissionsetline` - No schema changes
- `base_objects` - New page object records added

### Data Seeded

- 7 new page objects (IDs: 10302, 10402, 10801-10805)
- 3 new permission sets (USER*MGMT*\*)
- Updated 2 existing permission sets (PURCHASES_FULL, PAYMENTS_FULL)

---

## 🔒 Security Considerations

1. **Permission Verification**: All new API endpoints verify permissions
2. **JWT Token Security**: User must have valid token with page permissions
3. **Password Handling**: Reset password endpoint properly hashes passwords
4. **Auto-Save Fields**: All API calls are authenticated
5. **CORS**: Ensure production CORS settings are correct

---

## 📝 Rollback Plan

If you need to rollback:

### Backend Rollback

```bash
# 1. Remove new page objects
python manage.py shell --schema=<schema>
>>> from base.models import Objects
>>> Objects.objects.filter(object_id__in=[10302, 10402, 10801, 10802, 10803, 10804, 10805]).delete()
>>> exit()

# 2. Remove new permission sets (optional)
python manage.py shell --schema=<schema>
>>> from permissions.models import PermissionSet
>>> PermissionSet.objects.filter(code__startswith='USER_MGMT').delete()
>>> exit()

# 3. Revert code changes
git checkout <previous_commit_hash>

# 4. Restart application
```

### Frontend Rollback

```bash
# Revert to previous build
git checkout <previous_commit_hash>
npm run build
# Deploy previous dist folder
```

---

## 📞 Support

If you encounter issues during deployment:

1. Check server logs: `/var/log/zentroapp/` or `docker logs`
2. Check Django logs: Look for errors in console
3. Check browser console: F12 → Console tab
4. Check network tab: F12 → Network tab for API errors

---

## 🎉 Completion

Once all steps are complete:

1. ✅ Backend deployed and tested
2. ✅ Frontend deployed and tested
3. ✅ Permissions configured
4. ✅ Users notified to refresh tokens
5. ✅ All features tested
6. ✅ Documentation updated

**Congratulations! Your User Management System is now live in production!** 🚀

---

## 📌 Quick Reference

### Key Commands

```bash
# Deploy to specific tenant
./deploy_user_management.sh <schema>

# Check admin permissions
python manage.py tenant_command check_admin_permissions --schema=<schema>

# Populate page objects only
python manage.py tenant_command populate_page_objects --schema=<schema>

# Setup permissions only
python manage.py tenant_command setup_page_permissions --schema=<schema>
```

### Important URLs

- Django Admin: `http://your-domain/admin/`
- User Management: `http://your-domain/app/user-management/users`
- API Docs: `http://your-domain/api/swagger/`

### Key File Locations

- **Backend Scripts**: `zentro-backend/deploy_user_management.{sh,ps1}`
- **Page Objects**: `zentro-backend/base/management/commands/populate_page_objects.py`
- **Permissions**: `zentro-backend/permissions/management/commands/setup_page_permissions.py`
- **Frontend Nav**: `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts`
- **Frontend Routes**: `zentro-frontend/src/configs/routes.config/appsRoute.ts`
