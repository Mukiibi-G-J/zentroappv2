# Frontend User Group & Permission Set Management Implementation Plan

## Document Information

- **Created**: October 31, 2025
- **Status**: Planning Phase
- **Version**: 1.0
- **Related Docs**: [PERMISSIONS_SYSTEM_GUIDE.md](./PERMISSIONS_SYSTEM_GUIDE.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Implementation Objectives](#implementation-objectives)
4. [Architecture Overview](#architecture-overview)
5. [Implementation Phases](#implementation-phases)
6. [Technical Specifications](#technical-specifications)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Plan](#deployment-plan)

---

## Executive Summary

### Purpose

Extend the existing Django Admin user group and permission set management functionality to a full-featured frontend interface, allowing tenant administrators to manage users, roles, groups, and permissions without accessing the Django Admin panel.

### Scope

- **User Management**: Create, edit, delete users within tenant
- **User Group Management**: Create and manage user groups with role assignments
- **Permission Set Management**: Visual permission set builder and assignment
- **Role Center Management**: Configure role centers and module visibility
- **Role Management**: Create and manage roles with role center links

### Benefits

- **Self-Service**: Tenants can manage their own permissions without admin access
- **User-Friendly**: Modern UI/UX compared to Django Admin
- **Granular Control**: Visual permission management with real-time preview
- **Audit Trail**: Track who made permission changes and when
- **Mobile-Friendly**: Responsive design for tablet and mobile access

---

## Current State Analysis

### ✅ What Exists (Backend - Django Admin)

#### 1. **Data Models** (Complete)

- ✅ `CustomUser` model with user groups relationship
- ✅ `UserGroup` model with members and permission sets
- ✅ `Role` model with role center link
- ✅ `RoleCenter` model with module configuration
- ✅ `PermissionSet` model with permission lines
- ✅ `PermissionSetLine` model with CRUD permissions
- ✅ `Objects` model for application objects (pages, tables)

#### 2. **Admin Interface** (Complete)

- ✅ User admin with group display
- ✅ User group admin with filter horizontal for members/permission sets
- ✅ Permission set admin with inline permission lines
- ✅ Role admin with role center selection
- ✅ Role center admin with module JSON configuration

#### 3. **JWT Token Integration** (Complete)

- ✅ `user_groups` in JWT with codes, names, roles
- ✅ `permission_sets` in JWT with codes
- ✅ `role_center_modules` in JWT for navigation
- ✅ `page_permissions` in JWT with CRUD flags
- ✅ Token refresh maintains permission state

#### 4. **Frontend Hooks & Utilities** (Complete)

- ✅ `usePermissions()` hook with all permission checks
- ✅ Module visibility check (`isModuleVisible()`)
- ✅ Page access check (`canAccessPage()`)
- ✅ CRUD permission checks (`canCreate()`, `canEdit()`, etc.)
- ✅ User group checks (`isInGroup()`, `getUserGroups()`)

#### 5. **Navigation & Route Protection** (Complete)

- ✅ Sidebar filtering by module and page permissions
- ✅ Route protection with `pageName` checks
- ✅ Home page filtering by permissions

### ❌ What's Missing (Frontend Management UI)

#### 1. **User Management UI**

- ❌ User list page with search, filter, pagination
- ❌ User creation form with group assignment
- ❌ User edit form with group management
- ❌ User detail view with inherited permissions display
- ❌ Bulk user operations (activate/deactivate, assign groups)

#### 2. **User Group Management UI**

- ❌ User group list with member counts
- ❌ User group creation form
- ❌ User group edit form with member management
- ❌ Permission set assignment interface
- ❌ Role assignment (default profile) selector

#### 3. **Permission Set Management UI**

- ❌ Permission set list with permission counts
- ❌ Permission set builder with visual page selection
- ❌ CRUD permission toggles for each page
- ❌ Permission preview (what user can/cannot do)
- ❌ Permission set cloning

#### 4. **Role Center Management UI**

- ❌ Role center list with module displays
- ❌ Role center creation/edit form
- ❌ Module selector with checkboxes
- ❌ Feature configuration (optional)
- ❌ Dashboard widget configuration (optional)

#### 5. **Role Management UI**

- ❌ Role list with role center links
- ❌ Role creation/edit form
- ❌ Role center assignment
- ❌ Legacy permission management (optional)

#### 6. **API Endpoints**

- ❌ User CRUD endpoints for tenant users
- ❌ User group CRUD endpoints
- ❌ Permission set CRUD endpoints
- ❌ Permission set line CRUD endpoints
- ❌ Role center CRUD endpoints
- ❌ Role CRUD endpoints
- ❌ Objects list endpoint (for permission builder)

---

## Implementation Objectives

### Primary Goals

1. **Complete Feature Parity**: Match all Django Admin functionality
2. **Superior UX**: Provide better user experience than Django Admin
3. **Real-Time Updates**: Live permission preview and validation
4. **Mobile-Responsive**: Works on tablets and mobile devices
5. **Audit Trail**: Track all permission changes with timestamps

### User Stories

#### **As a Tenant Administrator**

- I want to create new users and assign them to groups
- I want to see what permissions each user has inherited
- I want to create custom user groups for different teams
- I want to build permission sets visually without editing JSON
- I want to preview what a user can see/do before saving changes
- I want to bulk assign users to groups
- I want to deactivate users without deleting them

#### **As a Manager**

- I want to see which users are in my team's group
- I want to request permission changes through the interface
- I want to understand what access my team members have

---

## Architecture Overview

### Frontend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Navigation Layer                      │
│  New Module: "User Management" (userManagement)         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ├─── Users Page (User List & CRUD)
                   ├─── User Groups Page (Group Management)
                   ├─── Permission Sets Page (Permission Builder)
                   ├─── Roles Page (Role Management)
                   └─── Role Centers Page (Module Configuration)

┌─────────────────────────────────────────────────────────┐
│                    Store Layer (Redux)                   │
│  - userManagementSlice (users, groups, roles)           │
│  - permissionSetSlice (permission sets & lines)         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                         │
│  - UserManagementService (API calls for users/groups)   │
│  - PermissionSetService (API calls for permissions)     │
│  - RoleService (API calls for roles/role centers)       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌─────────────────────────────────────────────────────────┐
│                    Backend API                           │
│  - /api/users/ (User CRUD)                              │
│  - /api/user-groups/ (User Group CRUD)                  │
│  - /api/permission-sets/ (Permission Set CRUD)          │
│  - /api/roles/ (Role CRUD)                              │
│  - /api/role-centers/ (Role Center CRUD)                │
│  - /api/objects/ (Application Objects for builder)      │
└─────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
UserManagement (Module Root)
│
├── Users
│   ├── UserList (Table with search/filter)
│   ├── UserForm (Create/Edit)
│   ├── UserDetail (View permissions)
│   └── components
│       ├── UserGroupSelector
│       ├── InheritedPermissionsDisplay
│       └── UserStatusBadge
│
├── UserGroups
│   ├── UserGroupList
│   ├── UserGroupForm
│   ├── UserGroupDetail
│   └── components
│       ├── MemberSelector (User multi-select)
│       ├── PermissionSetSelector (Multi-select)
│       ├── RoleSelector (Single select for default profile)
│       └── GroupPermissionPreview
│
├── PermissionSets
│   ├── PermissionSetList
│   ├── PermissionSetBuilder (Main form)
│   └── components
│       ├── ObjectSelector (By module)
│       ├── PermissionToggleGrid (CRUD checkboxes)
│       ├── PermissionPreview (What user can do)
│       └── PermissionSetCloner
│
├── Roles
│   ├── RoleList
│   ├── RoleForm
│   └── components
│       ├── RoleCenterSelector
│       └── LegacyPermissionEditor
│
└── RoleCenters
    ├── RoleCenterList
    ├── RoleCenterForm
    └── components
        ├── ModuleSelector (Checkboxes for modules)
        ├── FeatureConfig (Optional)
        └── DashboardWidgetConfig (Optional)
```

---

## Implementation Phases

### **Phase 1: Foundation & Backend APIs** ⬜

#### Objectives

- Create all necessary backend API endpoints
- Set up frontend service layer
- Configure routing and navigation
- Establish Redux store structure

#### Tasks

##### ✅ Checklist: Backend API Endpoints

**User Management Endpoints:**

- [ ] **POST** `/api/users/` - Create new user
  - Permissions: Admin or UserGroupManager role
  - Fields: email, username, full_name, phone_number, password, user_groups[]
  - Returns: User object with inherited permissions
- [ ] **GET** `/api/users/` - List all users (tenant-scoped)
  - Permissions: Admin or UserGroupManager
  - Query params: search, is_active, user_group, page, page_size
  - Returns: Paginated user list with group info
- [ ] **GET** `/api/users/{id}/` - Get user details
  - Permissions: Admin, UserGroupManager, or self
  - Returns: User with inherited roles, groups, and permissions
- [ ] **PUT/PATCH** `/api/users/{id}/` - Update user
  - Permissions: Admin or UserGroupManager
  - Fields: Same as create (except email)
  - Updates JWT if current user
- [ ] **DELETE** `/api/users/{id}/` - Delete user
  - Permissions: Admin only
  - Soft delete (set is_active=False)
- [ ] **POST** `/api/users/{id}/reset-password/` - Reset user password
  - Permissions: Admin or self (with old password)
- [ ] **POST** `/api/users/bulk-assign-groups/` - Bulk assign users to groups
  - Permissions: Admin or UserGroupManager
  - Body: { user_ids: [], group_ids: [] }

**User Group Endpoints:**

- [ ] **POST** `/api/user-groups/` - Create user group
  - Permissions: Admin
  - Fields: code, name, description, default_profile, permission_sets[], members[]
- [ ] **GET** `/api/user-groups/` - List user groups
  - Permissions: Admin or UserGroupManager
  - Query params: search, is_active, page, page_size
  - Returns: Groups with member counts and permission set counts
- [ ] **GET** `/api/user-groups/{id}/` - Get group details
  - Permissions: Admin or UserGroupManager
  - Returns: Group with full member list and permission sets
- [ ] **PUT/PATCH** `/api/user-groups/{id}/` - Update group
  - Permissions: Admin
  - Updates all group members' JWT on save
- [ ] **DELETE** `/api/user-groups/{id}/` - Delete group
  - Permissions: Admin only
  - Check for dependent users before delete
- [ ] **POST** `/api/user-groups/{id}/add-member/` - Add user to group
  - Permissions: Admin or UserGroupManager
  - Body: { user_id: number }
  - Updates user's JWT token
- [ ] **POST** `/api/user-groups/{id}/remove-member/` - Remove user from group
  - Permissions: Admin or UserGroupManager
  - Body: { user_id: number }
  - Updates user's JWT token

**Permission Set Endpoints:**

- [ ] **POST** `/api/permission-sets/` - Create permission set
  - Permissions: Admin only
  - Fields: code, name, description, permission_lines[]
  - Nested creation of permission lines
- [ ] **GET** `/api/permission-sets/` - List permission sets
  - Permissions: Admin or UserGroupManager (read-only)
  - Query params: search, is_active, page, page_size
  - Returns: Sets with permission line counts
- [ ] **GET** `/api/permission-sets/{id}/` - Get permission set details
  - Permissions: Admin or UserGroupManager
  - Returns: Set with all permission lines (eager loaded)
- [ ] **PUT/PATCH** `/api/permission-sets/{id}/` - Update permission set
  - Permissions: Admin only
  - Updates JWT for all users in groups using this set
- [ ] **DELETE** `/api/permission-sets/{id}/` - Delete permission set
  - Permissions: Admin only
  - Check for dependent user groups before delete
- [ ] **POST** `/api/permission-sets/{id}/clone/` - Clone permission set
  - Permissions: Admin only
  - Body: { new_code: string, new_name: string }
  - Creates duplicate with new code/name
- [ ] **GET** `/api/permission-sets/{id}/preview/` - Preview permissions
  - Permissions: Admin or UserGroupManager
  - Returns: Human-readable summary of what users can do

**Application Objects Endpoint:**

- [ ] **GET** `/api/objects/` - List application objects
  - Permissions: Admin or UserGroupManager
  - Query params: object_type (Page/Table/Report), module, requires_permission
  - Returns: Objects grouped by module for permission builder

**Role Endpoints:**

- [ ] **POST** `/api/roles/` - Create role
  - Permissions: Admin only
  - Fields: name, description, role_center, permissions (legacy)
- [ ] **GET** `/api/roles/` - List roles
  - Permissions: Admin or UserGroupManager (read-only)
  - Returns: Roles with role center info
- [ ] **GET** `/api/roles/{id}/` - Get role details
  - Permissions: Admin or UserGroupManager
- [ ] **PUT/PATCH** `/api/roles/{id}/` - Update role
  - Permissions: Admin only
  - Updates JWT for all users with this role
- [ ] **DELETE** `/api/roles/{id}/` - Delete role
  - Permissions: Admin only
  - Check for dependent user groups

**Role Center Endpoints:**

- [ ] **POST** `/api/role-centers/` - Create role center
  - Permissions: Admin only
  - Fields: code, name, description, modules[], features{}, dashboard_widgets[]
- [ ] **GET** `/api/role-centers/` - List role centers
  - Permissions: Admin or UserGroupManager (read-only)
- [ ] **GET** `/api/role-centers/{id}/` - Get role center details
  - Permissions: Admin or UserGroupManager
- [ ] **PUT/PATCH** `/api/role-centers/{id}/` - Update role center
  - Permissions: Admin only
  - Updates JWT for all users with roles linked to this center
- [ ] **DELETE** `/api/role-centers/{id}/` - Delete role center
  - Permissions: Admin only
  - Check for dependent roles

##### ✅ Checklist: Backend Serializers

- [ ] `UserSerializer` - Full user serialization with nested groups
- [ ] `UserListSerializer` - Lightweight for list views
- [ ] `UserGroupSerializer` - Group with member count and permission set info
- [ ] `UserGroupDetailSerializer` - Full group with all members and sets
- [ ] `PermissionSetSerializer` - Set with line count
- [ ] `PermissionSetDetailSerializer` - Set with all lines
- [ ] `PermissionSetLineSerializer` - Individual permission line
- [ ] `RoleSerializer` - Role with role center
- [ ] `RoleCenterSerializer` - Role center with module list
- [ ] `ObjectSerializer` - Application object for permission builder

##### ✅ Checklist: Frontend Service Layer

- [ ] Create `src/services/UserManagementService.ts`
  - CRUD operations for users
  - User search and filter
  - Password reset
  - Bulk operations
- [ ] Create `src/services/UserGroupService.ts`
  - CRUD operations for user groups
  - Add/remove members
  - Assign permission sets
- [ ] Create `src/services/PermissionSetService.ts`
  - CRUD operations for permission sets
  - Permission line management
  - Clone permission set
  - Permission preview
- [ ] Create `src/services/RoleService.ts`
  - CRUD operations for roles
  - Role center assignment
- [ ] Create `src/services/RoleCenterService.ts`
  - CRUD operations for role centers
  - Module configuration
- [ ] Create `src/services/ObjectService.ts`
  - Fetch application objects for permission builder
  - Group by module

##### ✅ Checklist: Redux Store Setup

- [ ] Create `src/store/slices/userManagement/userManagementSlice.ts`
  - State: users[], selectedUser, loading, error
  - Actions: fetchUsers, createUser, updateUser, deleteUser
  - Selectors: selectUsers, selectSelectedUser, selectUserById
- [ ] Create `src/store/slices/userManagement/userGroupSlice.ts`
  - State: groups[], selectedGroup, loading, error
  - Actions: fetchGroups, createGroup, updateGroup, deleteGroup
  - Selectors: selectGroups, selectSelectedGroup, selectGroupById
- [ ] Create `src/store/slices/userManagement/permissionSetSlice.ts`
  - State: sets[], selectedSet, objects[], loading, error
  - Actions: fetchSets, createSet, updateSet, deleteSet, fetchObjects
  - Selectors: selectSets, selectSelectedSet, selectObjects
- [ ] Create `src/store/slices/userManagement/roleSlice.ts`
  - State: roles[], roleCenters[], loading, error
  - Actions: fetchRoles, createRole, updateRole, deleteRole
  - Selectors: selectRoles, selectRoleCenters

##### ✅ Checklist: TypeScript Types

- [ ] Create `src/@types/userManagement.ts`

  ```typescript
  export interface User {
    id: number;
    email: string;
    username: string;
    full_name: string;
    phone_number: string;
    avatar?: string;
    is_active: boolean;
    is_staff: boolean;
    is_superuser: boolean;
    user_groups: UserGroup[];
    inherited_roles: Role[];
    inherited_permissions: PagePermissions[];
    created_at: string;
    updated_at: string;
  }

  export interface UserGroup {
    id: number;
    code: string;
    name: string;
    description?: string;
    default_profile?: Role;
    permission_sets: PermissionSet[];
    members: User[];
    member_count: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  }

  export interface PermissionSet {
    id: number;
    code: string;
    name: string;
    description?: string;
    permission_lines: PermissionSetLine[];
    line_count: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  }

  export interface PermissionSetLine {
    id: number;
    permissionset: number;
    application_object: ApplicationObject;
    read_permission: boolean;
    insert_permission: boolean;
    modify_permission: boolean;
    delete_permission: boolean;
    execute_permission: boolean;
  }

  export interface ApplicationObject {
    object_id: number;
    object_type: "Page" | "Table" | "Report";
    object_name: string;
    object_caption: string;
    object_subtype?: string;
    app_label: string; // module code
    requires_permission: boolean;
    is_active: boolean;
  }

  export interface Role {
    id: number;
    name: string;
    description?: string;
    role_center?: RoleCenter;
    permissions: string[]; // legacy
    is_active: boolean;
  }

  export interface RoleCenter {
    id: number;
    code: string;
    name: string;
    description?: string;
    modules: string[];
    features?: Record<string, string[]>;
    dashboard_widgets?: string[];
    is_active: boolean;
  }
  ```

##### ✅ Checklist: Routing & Navigation

- [ ] Add "User Management" module to navigation config

  ```typescript
  // src/configs/navigation.config/apps.navigation.config.ts
  {
    key: 'apps.userManagement',
    path: '',
    title: 'User Management',
    translateKey: 'nav.appsUserManagement.userManagement',
    icon: 'userManagement',
    type: NAV_ITEM_TYPE_COLLAPSE,
    authority: [],
    moduleCode: 'userManagement',
    subMenu: [
      {
        key: 'appsUserManagement.users',
        path: `${APP_PREFIX_PATH}/user-management/users`,
        title: 'Users',
        translateKey: 'nav.appsUserManagement.users',
        icon: '',
        type: NAV_ITEM_TYPE_ITEM,
        authority: [],
        pageName: 'User Management',
        subMenu: [],
      },
      {
        key: 'appsUserManagement.userGroups',
        path: `${APP_PREFIX_PATH}/user-management/user-groups`,
        title: 'User Groups',
        translateKey: 'nav.appsUserManagement.userGroups',
        icon: '',
        type: NAV_ITEM_TYPE_ITEM,
        authority: [],
        pageName: 'User Group Management',
        subMenu: [],
      },
      {
        key: 'appsUserManagement.permissionSets',
        path: `${APP_PREFIX_PATH}/user-management/permission-sets`,
        title: 'Permission Sets',
        translateKey: 'nav.appsUserManagement.permissionSets',
        icon: '',
        type: NAV_ITEM_TYPE_ITEM,
        authority: [],
        pageName: 'Permission Set Management',
        subMenu: [],
      },
      {
        key: 'appsUserManagement.roles',
        path: `${APP_PREFIX_PATH}/user-management/roles',
        title: 'Roles',
        translateKey: 'nav.appsUserManagement.roles',
        icon: '',
        type: NAV_ITEM_TYPE_ITEM,
        authority: [],
        pageName: 'Role Management',
        subMenu: [],
      },
      {
        key: 'appsUserManagement.roleCenters',
        path: `${APP_PREFIX_PATH}/user-management/role-centers`,
        title: 'Role Centers',
        translateKey: 'nav.appsUserManagement.roleCenters',
        icon: '',
        type: NAV_ITEM_TYPE_ITEM,
        authority: [],
        pageName: 'Role Center Management',
        subMenu: [],
      },
    ],
  }
  ```

- [ ] Add routes to `appsRoute.ts`

  ```typescript
  // User Management Routes
  {
    key: 'appsUserManagement.users',
    path: `${APP_PREFIX_PATH}/user-management/users`,
    component: lazy(() => import('@/views/user-management/Users')),
    authority: [],
    pageName: 'User Management',
  },
  {
    key: 'appsUserManagement.userGroups',
    path: `${APP_PREFIX_PATH}/user-management/user-groups`,
    component: lazy(() => import('@/views/user-management/UserGroups')),
    authority: [],
    pageName: 'User Group Management',
  },
  {
    key: 'appsUserManagement.permissionSets',
    path: `${APP_PREFIX_PATH}/user-management/permission-sets`,
    component: lazy(() => import('@/views/user-management/PermissionSets')),
    authority: [],
    pageName: 'Permission Set Management',
  },
  {
    key: 'appsUserManagement.roles',
    path: `${APP_PREFIX_PATH}/user-management/roles`,
    component: lazy(() => import('@/views/user-management/Roles')),
    authority: [],
    pageName: 'Role Management',
  },
  {
    key: 'appsUserManagement.roleCenters',
    path: `${APP_PREFIX_PATH}/user-management/role-centers`,
    component: lazy(() => import('@/views/user-management/RoleCenters')),
    authority: [],
    pageName: 'Role Center Management',
  },
  ```

- [ ] Add icon to `navigation-icon.config.tsx`

  ```typescript
  import { HiOutlineUserGroup } from 'react-icons/hi';

  userManagement: <HiOutlineUserGroup />,
  ```

##### ✅ Checklist: Backend Permission Setup

- [ ] Run `populate_page_objects.py` to add new pages

  ```python
  # User Management Pages (IDs: 10801-10810)
  (10801, "User Management", "userManagement", "Manage tenant users", "/app/user-management/users"),
  (10802, "User Group Management", "userManagement", "Manage user groups", "/app/user-management/user-groups"),
  (10803, "Permission Set Management", "userManagement", "Manage permission sets", "/app/user-management/permission-sets"),
  (10804, "Role Management", "userManagement", "Manage roles", "/app/user-management/roles"),
  (10805, "Role Center Management", "userManagement", "Manage role centers", "/app/user-management/role-centers"),
  ```

- [ ] Run `setup_page_permissions.py` to create permission sets

  ```python
  # User Management Permission Sets
  ("USER_MGMT_FULL", "User Management - Full Access", "Complete user management access", [
      ("User Management", "RIMD"),
      ("User Group Management", "RIMD"),
      ("Permission Set Management", "R"),
      ("Role Management", "R"),
      ("Role Center Management", "R"),
  ]),
  ("USER_MGMT_BASIC", "User Management - Basic", "Create/edit users and assign to groups", [
      ("User Management", "RIM"),
      ("User Group Management", "R"),
  ]),
  ("USER_MGMT_VIEW_ONLY", "User Management - View Only", "View users and groups", [
      ("User Management", "R"),
      ("User Group Management", "R"),
  ]),
  ```

- [ ] Add "userManagement" to Role Centers that should have access

---

### **Phase 2: User Management UI** ⬜

#### Objectives

- Build complete user management interface
- Enable user CRUD operations
- Display inherited permissions
- Implement bulk operations

#### Tasks

##### ✅ Checklist: User List Page

- [ ] Create `src/views/user-management/Users/UserList.tsx`
  - BaseTable integration with user columns
  - Search by email, username, full name
  - Filter by user group, active status
  - Sort by name, email, created date
  - Actions: Edit, Delete (soft), Reset Password
- [ ] Define user columns in `src/views/user-management/Users/constants/userColumns.tsx`

  ```typescript
  export const userColumns = [
    { header: "Email", accessorKey: "email", enableSorting: true },
    { header: "Full Name", accessorKey: "full_name", enableSorting: true },
    { header: "Username", accessorKey: "username", enableSorting: true },
    {
      header: "Groups",
      accessorKey: "user_groups",
      cell: (row) => GroupBadges,
    },
    { header: "Status", accessorKey: "is_active", cell: (row) => StatusBadge },
    { header: "Created", accessorKey: "created_at", enableSorting: true },
    // Actions column handled by BaseTable
  ];
  ```

- [ ] Create user status badge component

  - `src/views/user-management/Users/components/UserStatusBadge.tsx`
  - Green for active, gray for inactive
  - Shows is_staff/is_superuser badges if applicable

- [ ] Implement user search/filter
  - Real-time search with debounce
  - Multi-select for user groups
  - Active/inactive toggle
  - Clear all filters button

##### ✅ Checklist: User Form (Create/Edit)

- [ ] Create `src/views/user-management/Users/UserForm.tsx`
  - Form fields:
    - Email (required, validated)
    - Username (required, auto-generated option)
    - Full Name (required)
    - Phone Number (required, formatted)
    - Password (required for create, optional for edit)
    - User Groups (multi-select with search)
    - Avatar upload (optional)
    - Is Active checkbox
    - Is Staff checkbox (admin only)
    - Is Superuser checkbox (admin only)
- [ ] Create `src/views/user-management/Users/components/UserGroupSelector.tsx`
  - Multi-select dropdown with search
  - Display selected groups as badges
  - Show inherited role for each group
  - Tooltip on hover showing permission sets
- [ ] Form validation
  - Email format validation
  - Username uniqueness check (debounced API call)
  - Phone number format validation
  - Password strength indicator
  - Required field validation
- [ ] Auto-save functionality
  - Save draft to local storage
  - Restore on page reload
  - Clear on successful submit

##### ✅ Checklist: User Detail View

- [ ] Create `src/views/user-management/Users/UserDetail.tsx`
  - User info card (avatar, name, email, phone)
  - Group memberships section
  - Inherited roles section
  - Inherited permissions section (grouped by module)
  - Activity log section
  - Action buttons: Edit, Reset Password, Deactivate
- [ ] Create `src/views/user-management/Users/components/InheritedPermissionsDisplay.tsx`
  - Accordion by module
  - Each module shows:
    - Pages user can access
    - CRUD permissions for each page (color-coded badges)
    - Permission source (which group/permission set)
  - Search/filter within permissions
  - Export permissions report (PDF/CSV)

##### ✅ Checklist: Bulk Operations

- [ ] Implement row selection in UserList
  - Checkbox column
  - Select all/none
  - Show selected count
- [ ] Bulk action bar
  - Appears when rows selected
  - Actions:
    - Activate selected
    - Deactivate selected
    - Assign to group
    - Remove from group
    - Delete selected (confirm modal)
    - Export selected (CSV)

##### ✅ Checklist: User Deletion

- [ ] Create confirmation modal
  - Show user details
  - Warn about consequences
  - Require confirmation text entry for important users
  - Option: Hard delete vs Soft delete (deactivate)
- [ ] Implement soft delete
  - Set is_active = False
  - Preserve data for audit
  - Can be reactivated later
- [ ] Check for dependencies
  - Warn if user is in groups
  - Warn if user has created records
  - Option to reassign ownership

##### ✅ Checklist: Password Reset

- [ ] Create password reset modal
  - Option 1: Generate random password and email
  - Option 2: Set manual password
  - Password strength indicator
  - Send reset email checkbox
  - Success notification with next steps

---

### **Phase 3: User Group Management UI** ⬜

#### Objectives

- Build user group management interface
- Enable visual member management
- Implement permission set assignment
- Show permission preview

#### Tasks

##### ✅ Checklist: User Group List Page

- [ ] Create `src/views/user-management/UserGroups/UserGroupList.tsx`
  - BaseTable with group columns
  - Search by name, code
  - Filter by default role, active status
  - Sort by name, member count, created date
  - Actions: Edit, Delete, View Details
- [ ] Define group columns

  ```typescript
  export const userGroupColumns = [
    { header: "Name", accessorKey: "name", enableSorting: true },
    { header: "Code", accessorKey: "code", enableSorting: true },
    { header: "Default Role", accessorKey: "default_profile.name" },
    { header: "Members", accessorKey: "member_count", enableSorting: true },
    {
      header: "Permission Sets",
      accessorKey: "permission_sets",
      cell: CountBadge,
    },
    { header: "Status", accessorKey: "is_active", cell: StatusBadge },
    { header: "Created", accessorKey: "created_at", enableSorting: true },
  ];
  ```

- [ ] Create group stat cards
  - Total groups
  - Active groups
  - Total members across all groups
  - Average members per group

##### ✅ Checklist: User Group Form

- [ ] Create `src/views/user-management/UserGroups/UserGroupForm.tsx`

  - Basic Info Section:

    - Code (required, uppercase, no spaces)
    - Name (required)
    - Description (optional, markdown support)
    - Is Active checkbox

  - Role Assignment Section:

    - Default Profile selector (dropdown with role search)
    - Show linked role center and modules
    - Warning if role has no role center

  - Permission Sets Section:

    - Multi-select with search
    - Show permission line count for each set
    - Preview button for each set
    - Add new permission set button (opens modal)

  - Members Section:
    - User multi-select with search
    - Show current members in table
    - Bulk add/remove
    - Show inherited role for each member

- [ ] Create `src/views/user-management/UserGroups/components/MemberSelector.tsx`

  - Transfer list component
  - Available users on left, selected on right
  - Search in both lists
  - Select all/none buttons
  - Shows user groups already assigned to users

- [ ] Create `src/views/user-management/UserGroups/components/PermissionSetSelector.tsx`

  - Multi-select dropdown with checkboxes
  - Search by name/code
  - Show permission line count
  - Color-coded by coverage (full/partial/minimal)
  - Quick preview icon for each set

- [ ] Create `src/views/user-management/UserGroups/components/RoleSelector.tsx`
  - Single-select dropdown
  - Show role center name and modules
  - Option to create new role inline
  - Show warning if role has no role center

##### ✅ Checklist: Permission Preview

- [ ] Create `src/views/user-management/UserGroups/components/GroupPermissionPreview.tsx`
  - Modal dialog
  - Tabs by module
  - Each tab shows:
    - Pages accessible
    - CRUD permissions (color-coded matrix)
    - Which permission set grants access
  - "Simulate User" mode - enter user email to see their combined permissions
  - Export preview as PDF
- [ ] Permission conflict detection
  - Show if multiple permission sets conflict
  - Highlight which permission set wins (OR logic)
  - Warn about overly permissive combinations

##### ✅ Checklist: Group Detail View

- [ ] Create `src/views/user-management/UserGroups/UserGroupDetail.tsx`
  - Group info card
  - Members table (paginated)
  - Permission sets table
  - Permission preview section
  - Audit log (who added/removed members, permission changes)
- [ ] Member management within detail view
  - Add member button
  - Remove member button (with confirm)
  - Show inherited permissions for each member
  - Filter/search members

---

### **Phase 4: Permission Set Builder UI** ⬜

#### Objectives

- Build visual permission set builder
- Enable granular CRUD permission assignment
- Implement permission preview
- Add permission set cloning

#### Tasks

##### ✅ Checklist: Permission Set List Page

- [ ] Create `src/views/user-management/PermissionSets/PermissionSetList.tsx`
  - BaseTable with permission set columns
  - Search by name, code
  - Filter by module, line count
  - Sort by name, line count, created date
  - Actions: Edit, Clone, Delete, Preview
- [ ] Define permission set columns

  ```typescript
  export const permissionSetColumns = [
    { header: "Name", accessorKey: "name", enableSorting: true },
    { header: "Code", accessorKey: "code", enableSorting: true },
    { header: "Permissions", accessorKey: "line_count", enableSorting: true },
    { header: "Groups Using", accessorKey: "user_group_count" },
    { header: "Status", accessorKey: "is_active", cell: StatusBadge },
    { header: "Created", accessorKey: "created_at", enableSorting: true },
  ];
  ```

- [ ] Permission set stat cards
  - Total permission sets
  - Active permission sets
  - Most used permission set
  - Average permissions per set

##### ✅ Checklist: Permission Set Builder

- [ ] Create `src/views/user-management/PermissionSets/PermissionSetBuilder.tsx`

  - Three-column layout:

    1. Basic info & object selector (left sidebar)
    2. Permission grid (center)
    3. Preview pane (right sidebar, collapsible)

  - Basic Info Section:

    - Code (required, uppercase)
    - Name (required)
    - Description (optional, markdown)
    - Is Active checkbox

  - Object Selector:

    - Accordion by module
    - Each module shows pages/tables/reports
    - Checkbox to select objects
    - Search within modules
    - Bulk select all in module

  - Permission Grid:

    - Rows: Selected objects
    - Columns: Read, Insert, Modify, Delete, Execute
    - Checkboxes for each permission
    - Color-coded by permission type
    - Quick actions: Grant all, Revoke all
    - Row actions: Remove from set

  - Preview Pane:
    - Live preview of what users can do
    - Grouped by module
    - Human-readable descriptions
    - "User can create sales invoices" etc.

- [ ] Create `src/views/user-management/PermissionSets/components/ObjectSelector.tsx`
  - Tree view by module
  - Checkbox selection
  - Search/filter
  - Show object type icons (Page/Table/Report)
  - Badge showing permission count for selected objects
- [ ] Create `src/views/user-management/PermissionSets/components/PermissionToggleGrid.tsx`

  - Data table with CRUD columns
  - Checkbox toggles for each permission
  - Tooltips explaining each permission
  - Keyboard navigation (arrow keys)
  - Bulk operations:
    - Select all rows
    - Select all columns
    - Clear selection
    - Apply permission template

- [ ] Create `src/views/user-management/PermissionSets/components/PermissionPreview.tsx`
  - Collapsible right sidebar
  - Real-time updates as permissions change
  - Tabs: By Module, By Permission Type, Summary
  - Warning/info messages:
    - "This grants access to X pages"
    - "Users can create but not edit"
    - "Potential security risk: Full delete access"

##### ✅ Checklist: Permission Set Cloning

- [ ] Create clone modal
  - Source permission set preview
  - New code (required, must be unique)
  - New name (required)
  - Copy description checkbox
  - Modify permissions before save checkbox
  - Clone button creates and opens in builder

##### ✅ Checklist: Permission Templates

- [ ] Create template system
  - Predefined templates:
    - Full Access (RIMDX on all objects)
    - Read-Only (R on all objects)
    - Create-Only (RI on specific objects)
    - Manager (RIM on most, D on some)
  - Apply template to selected objects
  - Save custom templates
  - Share templates across tenant

##### ✅ Checklist: Permission Set Validation

- [ ] Validate before save
  - Check for empty permission sets (warn)
  - Check for dangerous combinations (warn)
  - Check for conflicts with existing sets (warn)
  - Require confirmation if used by active groups
- [ ] Dependency check on delete
  - Show which groups use this set
  - Show affected user count
  - Option: Delete or replace with another set
  - Require confirmation

---

### **Phase 5: Role & Role Center Management UI** ⬜

#### Objectives

- Build role management interface
- Build role center configuration UI
- Enable module selection for role centers
- Link roles to role centers

#### Tasks

##### ✅ Checklist: Role List Page

- [ ] Create `src/views/user-management/Roles/RoleList.tsx`
  - BaseTable with role columns
  - Search by name
  - Filter by role center, active status
  - Sort by name, created date
  - Actions: Edit, Delete, View Details
- [ ] Define role columns
  ```typescript
  export const roleColumns = [
    { header: "Name", accessorKey: "name", enableSorting: true },
    { header: "Role Center", accessorKey: "role_center.name" },
    {
      header: "Modules",
      accessorKey: "role_center.modules",
      cell: ModuleBadges,
    },
    { header: "Groups Using", accessorKey: "user_group_count" },
    { header: "Status", accessorKey: "is_active", cell: StatusBadge },
    { header: "Created", accessorKey: "created_at", enableSorting: true },
  ];
  ```

##### ✅ Checklist: Role Form

- [ ] Create `src/views/user-management/Roles/RoleForm.tsx`

  - Basic Info Section:

    - Name (required)
    - Description (optional, markdown)
    - Is Active checkbox

  - Role Center Section:

    - Role center selector (dropdown)
    - Preview modules in selected role center
    - Option to create new role center inline
    - Show which modules will be visible

  - Legacy Permissions Section (collapsible):
    - JSON editor for old-style permissions
    - Warning: "Use Role Centers and Permission Sets instead"
    - Migration helper: Convert to role center

- [ ] Create `src/views/user-management/Roles/components/RoleCenterSelector.tsx`
  - Dropdown with search
  - Shows modules for each role center
  - Create new option
  - Preview card shows:
    - Modules included
    - Features (if any)
    - Dashboard widgets (if any)

##### ✅ Checklist: Role Center List Page

- [ ] Create `src/views/user-management/RoleCenters/RoleCenterList.tsx`
  - BaseTable with role center columns
  - Search by name, code
  - Filter by module count, active status
  - Sort by name, created date
  - Actions: Edit, Delete, Clone
- [ ] Define role center columns
  ```typescript
  export const roleCenterColumns = [
    { header: "Name", accessorKey: "name", enableSorting: true },
    { header: "Code", accessorKey: "code", enableSorting: true },
    { header: "Modules", accessorKey: "modules", cell: ModuleBadges },
    { header: "Roles Using", accessorKey: "role_count" },
    { header: "Status", accessorKey: "is_active", cell: StatusBadge },
    { header: "Created", accessorKey: "created_at", enableSorting: true },
  ];
  ```

##### ✅ Checklist: Role Center Form

- [ ] Create `src/views/user-management/RoleCenters/RoleCenterForm.tsx`

  - Basic Info Section:

    - Code (required, uppercase)
    - Name (required)
    - Description (optional, markdown)
    - Is Active checkbox

  - Module Selection Section:

    - Grid of module checkboxes
    - Icons for each module
    - Select all/none
    - Show page count for each module
    - Preview selected modules

  - Advanced Configuration (collapsible):
    - Features per module (JSON editor)
    - Dashboard widgets (multi-select)
    - Help text and examples

- [ ] Create `src/views/user-management/RoleCenters/components/ModuleSelector.tsx`

  - Grid layout (3-4 columns)
  - Each module card:
    - Icon
    - Name
    - Description
    - Page count
    - Checkbox
  - Available modules:
    - sales, customers, items, purchases
    - payments, expenses, financials
    - hotel, reports, settings, etc.

- [ ] Create `src/views/user-management/RoleCenters/components/ModulePreview.tsx`
  - Shows selected modules
  - For each module:
    - List of pages included
    - Navigation structure preview
    - Example screenshots (optional)

##### ✅ Checklist: Role Center Cloning

- [ ] Create clone modal
  - Source role center preview
  - New code (required, must be unique)
  - New name (required)
  - Copy modules checkbox (default true)
  - Copy features checkbox (default false)
  - Clone button creates new role center

---

### **Phase 6: UX Enhancements & Polish** ⬜

#### Objectives

- Add advanced features
- Improve user experience
- Add help documentation
- Implement audit logging

#### Tasks

##### ✅ Checklist: Search & Filtering

- [ ] Global search across all entities
  - Search bar in header
  - Results grouped by type (users, groups, sets, roles)
  - Quick actions from search results
  - Recent searches history
- [ ] Advanced filtering
  - Filter panel (collapsible sidebar)
  - Multiple filter criteria
  - Saved filter presets
  - Export filtered results

##### ✅ Checklist: Audit Logging

- [ ] Create audit log viewer
  - List all permission changes
  - Filter by user, action, date range
  - Show before/after for changes
  - Export audit logs (CSV/PDF)
- [ ] Audit log details
  - User who made change
  - Timestamp
  - Action type (create/update/delete)
  - Entity affected
  - Changes made (diff view)
  - IP address and user agent

##### ✅ Checklist: Help & Documentation

- [ ] Inline help tooltips
  - Every form field has help tooltip
  - Examples and best practices
  - Links to detailed docs
- [ ] Help panel (collapsible)
  - Context-sensitive help
  - Video tutorials (embedded)
  - Links to docs
  - FAQ section
- [ ] Onboarding tour
  - First-time user tour
  - Highlights key features
  - Interactive examples
  - Skip/restart options

##### ✅ Checklist: Notifications

- [ ] Toast notifications
  - Success: User created, group updated, etc.
  - Warning: Validation issues, conflicts
  - Error: API failures, permission denied
  - Auto-dismiss with undo option
- [ ] Activity notifications
  - Real-time updates when permissions change
  - Notify affected users
  - Email notifications for important changes

##### ✅ Checklist: Accessibility

- [ ] Keyboard navigation
  - Tab order makes sense
  - Shortcuts for common actions
  - Focus indicators visible
  - Skip links for screen readers
- [ ] ARIA labels
  - All interactive elements labeled
  - Semantic HTML structure
  - Proper heading hierarchy
  - Form validation accessible
- [ ] Color contrast
  - WCAG AA compliance
  - High contrast mode support
  - Icons don't rely solely on color

##### ✅ Checklist: Performance

- [ ] Lazy loading
  - Load users/groups on demand
  - Infinite scroll for large lists
  - Virtual scrolling for permission grids
- [ ] Caching
  - Cache permission sets
  - Cache role centers
  - Invalidate on changes
- [ ] Optimistic updates
  - Instant UI feedback
  - Rollback on error
  - Show loading states

##### ✅ Checklist: Responsive Design

- [ ] Mobile layout
  - Collapsible sidebars
  - Touch-friendly buttons
  - Swipe gestures
  - Simplified forms on small screens
- [ ] Tablet layout
  - Side-by-side panels
  - Landscape optimized
  - Stylus support

##### ✅ Checklist: Export/Import

- [ ] Export functionality
  - Export users (CSV)
  - Export groups (JSON)
  - Export permission sets (JSON)
  - Export audit logs (CSV/PDF)
- [ ] Import functionality
  - Import users from CSV
  - Import permission sets from JSON
  - Validation before import
  - Preview import results
  - Rollback option

---

## Technical Specifications

### Backend API Details

#### Authentication & Authorization

- All endpoints require authentication (JWT)
- Admin or UserGroupManager role required for most endpoints
- Users can view their own profile without elevated permissions
- Permission checks before all write operations

#### Pagination

- Default page size: 20
- Max page size: 100
- Response format:
  ```json
  {
    "count": 150,
    "next": "http://api/users/?page=2",
    "previous": null,
    "results": [...]
  }
  ```

#### Error Handling

- Standard HTTP status codes
- Error response format:
  ```json
  {
    "error": "Validation failed",
    "detail": "Email already exists",
    "field": "email",
    "code": "unique_constraint"
  }
  ```

#### Real-Time Updates

- WebSocket connections for real-time permission updates
- Broadcast to affected users when permissions change
- Force JWT refresh for affected users

### Frontend Patterns (Following Existing UI Design)

#### 🎨 **CRITICAL: Match Existing UI Design System**

The implementation **MUST** follow the exact patterns used in existing pages like `Customers.tsx`, `Items.tsx`, and `RoleManagement.tsx`:

#### Component Structure (Exactly Like Current Pages)

```typescript
// PATTERN: BaseCard + BaseTable combination
// Used in: Customers.tsx, Items.tsx, RoleManagement.tsx
<>
  <BaseCard
    title="User"
    height={700}
    width={1200}
    systemId={currentUser?.id}
    loading={isSaving}
    isOpen={isOpen}
    onOpen={handleOpen}
    onClose={handleClose}
    statusBar={
      isSaving ? (
        <div className="sticky top-0 z-50 w-full bg-yellow-100 text-yellow-800 text-center py-2 font-medium shadow-sm">
          Saving...
        </div>
      ) : showSaved ? (
        <div className="sticky top-0 z-50 w-full bg-green-100 text-green-800 text-center py-2 font-medium shadow-sm">
          Saved
        </div>
      ) : null
    }
  >
    <div className="p-4">
      <Formik {...props}>
        {() => (
          <Form>
            <Card className="mb-4">
              <h4 className="mb-4">Section Title</h4>
              <FormContainer>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <AutoSaveField {...fieldProps} />
                </div>
              </FormContainer>
            </Card>
          </Form>
        )}
      </Formik>
    </div>
  </BaseCard>

  <BaseTable
    title="Users"
    columns={columns}
    data={data}
    loading={loading}
    tableData={tableData}
    isCardModalOpen={isOpen}
    onEdit={showEditButton ? handleEdit : undefined}
    onDelete={showDeleteButton ? handleDelete : undefined}
    onSearch={handleSearch}
    onFilter={handleFilter}
    onPaginationChange={handlePaginationChange}
    onSort={handleSort}
    onAdd={showCreateButton ? handleAdd : undefined}
  />
</>
```

#### Auto-Save Pattern (Critical!)

```typescript
// PATTERN: AutoSaveField component with auto-save on blur/change
// Used in: Customers.tsx, Items.tsx, RoleManagement.tsx

const AutoSaveField = ({
  name,
  label,
  placeholder,
  type = "text",
  setIsSaving,
  setShowSaved,
}: AutoSaveFieldProps) => {
  const formik = useFormikContext<FormValues>();

  const handleBlur = async (e: React.FocusEvent<HTMLInputElement>) => {
    try {
      setIsSaving(true);

      if (currentItem.id) {
        // Update existing
        const response = await Service.update(currentItem.id, {
          [name]: e.target.value,
        });
        dispatch(actions.setCurrentRec(response.data));
      } else {
        // Create new
        const response = await Service.create({ [name]: e.target.value });
        dispatch(actions.setCurrentRec(response.data));
      }

      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (error) {
      toast.push(
        <Notification title="Error" type="danger" duration={2500}>
          {getErrorMessage(error)}
        </Notification>
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <FormItem label={label}>
      <Input
        name={name}
        placeholder={placeholder}
        value={formik.values[name]}
        onChange={(e) => formik.setFieldValue(name, e.target.value)}
        onBlur={handleBlur}
      />
    </FormItem>
  );
};
```

#### State Management Pattern

```typescript
// PATTERN: Redux slice with specific structure
// Used in: customerSlice.ts, itemSlice.ts, roleSlice.ts

const slice = createSlice({
  name: "users",
  initialState: {
    data: [],
    currentRec: null,
    loading: false,
    tableData: {
      pageIndex: 1,
      pageSize: 10,
      total: 0,
      query: "",
      sort: null,
    },
    filterData: {},
  },
  reducers: {
    setData: (state, action) => {
      state.data = action.payload;
    },
    setCurrentRec: (state, action) => {
      state.currentRec = action.payload;
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
    setTableData: (state, action) => {
      state.tableData = { ...state.tableData, ...action.payload };
    },
    setFilterData: (state, action) => {
      state.filterData = action.payload;
    },
  },
});
```

#### Modal Management Pattern

```typescript
// PATTERN: useTableModal hook for modal state
// Used in: All CRUD pages

const { isOpen, openModal, closeModal, setModalOpen } =
  useTableModal(userActions);

const handleEdit = useCallback(
  (row: User) => {
    dispatch(userActions.setCurrentRec(row));
    setModalOpen(true);
  },
  [dispatch, setModalOpen]
);

const handleOpen = useCallback(() => {
  dispatch(userActions.setCurrentRec(null));
  openModal();
}, [dispatch, openModal]);

const handleClose = () => {
  resetForm();
  closeModal();
};
```

#### Form Layout Pattern

```typescript
// PATTERN: Two-column grid layout with Card sections
// Used in: Items.tsx, RoleManagement.tsx

<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* Left Column */}
  <div className="space-y-4">
    <Card className="p-4">
      <h4 className="text-lg font-semibold text-gray-900 mb-4">
        Basic Information
      </h4>
      <FormContainer>
        <AutoSaveField name="field1" label="Field 1" {...props} />
        <AutoSaveField name="field2" label="Field 2" {...props} />
      </FormContainer>
    </Card>
  </div>

  {/* Right Column */}
  <div className="space-y-4">
    <Card className="p-4">
      <h4 className="text-lg font-semibold text-gray-900 mb-4">
        Additional Details
      </h4>
      <FormContainer>
        <AutoSaveField name="field3" label="Field 3" {...props} />
      </FormContainer>
    </Card>
  </div>
</div>
```

#### Permission Checks Pattern

```typescript
// PATTERN: usePermissions hook for UI control
// Used in: Customers.tsx, Items.tsx

const { canCreate, canEdit, canDelete } = usePermissions();
const PAGE_NAME = "User Management";
const showCreateButton = canCreate(PAGE_NAME);
const showEditButton = canEdit(PAGE_NAME);
const showDeleteButton = canDelete(PAGE_NAME);

// In render:
<BaseTable
  onEdit={showEditButton ? handleEdit : undefined}
  onDelete={showDeleteButton ? handleDelete : undefined}
  onAdd={showCreateButton ? handleAdd : undefined}
/>;
```

#### Toast Notification Pattern

```typescript
// PATTERN: Toast + Notification for feedback
// Used in: All CRUD pages

toast.push(
  <Notification title="Success" type="success" duration={2500}>
    User created successfully
  </Notification>
);

toast.push(
  <Notification title="Error" type="danger" duration={2500}>
    {getErrorMessage(error)}
  </Notification>
);
```

#### Column Definition Pattern

```typescript
// PATTERN: Column definitions in constants folder
// Used in: customerColumns.tsx, roleColumns.tsx

export const useUserColumns = () => {
  return useMemo<ColumnDef<User>[]>(
    () => [
      {
        header: "Email",
        accessorKey: "email",
        enableSorting: true,
      },
      {
        header: "Full Name",
        accessorKey: "full_name",
        enableSorting: true,
      },
      {
        header: "Groups",
        accessorKey: "user_groups",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.user_groups?.map((group) => (
              <Badge key={group.id}>{group.name}</Badge>
            ))}
          </div>
        ),
      },
      {
        header: "Status",
        accessorKey: "is_active",
        cell: ({ row }) => (
          <Badge
            className={row.original.is_active ? "bg-green-100" : "bg-gray-100"}
          >
            {row.original.is_active ? "Active" : "Inactive"}
          </Badge>
        ),
      },
    ],
    []
  );
};
```

#### Error Handling Pattern

```typescript
// PATTERN: getErrorMessage utility for consistent error handling
// Used in: All service calls

try {
  // API call
} catch (error) {
  toast.push(
    <Notification title="Error" type="danger" duration={2500}>
      {getErrorMessage(error)}
    </Notification>
  );
}
```

#### Key UI Specifications

1. **Modal Sizes**: BaseCard `height={600-700}` `width={1000-1200}`
2. **Grid Layout**: `grid grid-cols-1 md:grid-cols-2 gap-4` for forms
3. **Card Spacing**: `mb-4` between Card sections
4. **Status Bar**: Sticky top-0 z-50 w-full (yellow for saving, green for saved)
5. **Form Container**: Use `FormContainer` wrapper for form sections
6. **Loading States**: Show loading prop on BaseCard and BaseTable
7. **Toast Duration**: 2500ms for all notifications
8. **Button Variants**: `variant="solid"` for primary actions
9. **Icons**: Use HeroIcons (Hi prefix) from react-icons
10. **Responsive**: Use `lg:grid-cols-2` for responsive layouts

### Security Considerations

#### Frontend

- No sensitive data in localStorage (only JWT)
- CSRF protection for all mutations
- XSS prevention (sanitize user input)
- Content Security Policy headers

#### Backend

- Rate limiting on API endpoints
- SQL injection prevention (ORM usage)
- Permission checks before all operations
- Audit all permission changes

---

## Testing Strategy

### Unit Tests

#### Backend

- [ ] Test user creation with groups
- [ ] Test permission inheritance
- [ ] Test JWT token generation
- [ ] Test permission checks
- [ ] Test bulk operations

#### Frontend

- [ ] Test permission utils functions
- [ ] Test Redux actions/reducers
- [ ] Test component rendering
- [ ] Test form validation
- [ ] Test search/filter logic

### Integration Tests

- [ ] Test user creation flow end-to-end
- [ ] Test group assignment updates JWT
- [ ] Test permission changes reflect in UI
- [ ] Test bulk user operations
- [ ] Test permission preview accuracy

### E2E Tests

- [ ] Admin creates user and assigns to group
- [ ] User logs in and sees correct modules
- [ ] Permission set changes update user access
- [ ] Group member changes update permissions
- [ ] Audit log records all changes

### Manual Testing Checklist

#### User Management

- [ ] Create user with multiple groups
- [ ] Edit user and change groups
- [ ] Delete user (soft delete)
- [ ] Reset user password
- [ ] Bulk assign users to groups
- [ ] Search and filter users

#### User Group Management

- [ ] Create group with role and permission sets
- [ ] Add/remove members
- [ ] Change default role
- [ ] Add/remove permission sets
- [ ] View permission preview
- [ ] Delete group

#### Permission Set Management

- [ ] Create permission set from scratch
- [ ] Add permissions for multiple modules
- [ ] Clone permission set
- [ ] Edit existing permission set
- [ ] Delete permission set
- [ ] Preview permissions

#### Role & Role Center Management

- [ ] Create role center with modules
- [ ] Create role and link to role center
- [ ] User logs in and sees correct modules
- [ ] Change role center modules
- [ ] User refreshes and sees updated modules

---

## Deployment Plan

### Pre-Deployment

- [ ] Complete all unit tests
- [ ] Complete integration tests
- [ ] Complete E2E tests
- [ ] Code review for all components
- [ ] Security audit
- [ ] Performance testing
- [ ] Documentation complete

### Deployment Steps

1. **Database Migration**

   - [ ] Run migrations on staging
   - [ ] Verify no data loss
   - [ ] Test rollback procedure

2. **Backend Deployment**

   - [ ] Deploy API endpoints
   - [ ] Run `populate_page_objects.py`
   - [ ] Run `setup_page_permissions.py`
   - [ ] Verify endpoints work

3. **Frontend Deployment**

   - [ ] Build production bundle
   - [ ] Deploy to CDN
   - [ ] Verify routes work
   - [ ] Test on staging

4. **Post-Deployment**
   - [ ] Create default admin group
   - [ ] Assign admin users to group
   - [ ] Test full user creation flow
   - [ ] Monitor error logs
   - [ ] Verify JWT tokens work

### Rollback Plan

- [ ] Revert frontend to previous version
- [ ] Revert backend to previous version
- [ ] Rollback database migrations
- [ ] Notify affected users
- [ ] Document issues for next attempt

---

## Timeline Estimates

### Phase 1: Foundation (Backend APIs, Services, Store)

- **Duration**: 2-3 weeks
- **Effort**: ~80 hours
- **Team**: 2 backend + 1 frontend developer

### Phase 2: User Management UI

- **Duration**: 2 weeks
- **Effort**: ~60 hours
- **Team**: 2 frontend developers

### Phase 3: User Group Management UI

- **Duration**: 1.5 weeks
- **Effort**: ~50 hours
- **Team**: 2 frontend developers

### Phase 4: Permission Set Builder UI

- **Duration**: 2.5 weeks
- **Effort**: ~80 hours
- **Team**: 2 frontend developers
- **Note**: Most complex UI component

### Phase 5: Role & Role Center Management UI

- **Duration**: 1 week
- **Effort**: ~40 hours
- **Team**: 1 frontend developer

### Phase 6: UX Enhancements & Polish

- **Duration**: 1.5 weeks
- **Effort**: ~50 hours
- **Team**: 1 frontend + 1 UX designer

### **Total Estimated Duration**: 10-11 weeks

### **Total Estimated Effort**: ~360 hours

---

## Success Criteria

### Functional Requirements Met

- [ ] All CRUD operations work for users, groups, permission sets, roles, role centers
- [ ] Permission inheritance works correctly
- [ ] JWT tokens update when permissions change
- [ ] Navigation filters correctly by permissions
- [ ] Audit logging captures all changes

### Performance Metrics

- [ ] User list loads in < 2 seconds (1000 users)
- [ ] Permission preview generates in < 1 second
- [ ] Search results return in < 500ms
- [ ] Page load time < 3 seconds on 3G connection

### User Experience

- [ ] Admin can complete full user setup in < 5 minutes
- [ ] Permission set builder is intuitive (no training needed)
- [ ] Mobile usable (80%+ features work on phone)
- [ ] Accessibility compliant (WCAG AA)

### Security

- [ ] All permission checks enforced
- [ ] Audit trail complete
- [ ] No permission escalation vulnerabilities
- [ ] Rate limiting prevents abuse

---

## Known Risks & Mitigation

### Risk 1: Performance with Large Permission Sets

- **Impact**: High
- **Probability**: Medium
- **Mitigation**:
  - Implement pagination
  - Use virtual scrolling
  - Cache permission sets
  - Lazy load permission lines

### Risk 2: Complex Permission Inheritance Logic

- **Impact**: High
- **Probability**: High
- **Mitigation**:
  - Extensive testing
  - Clear documentation
  - Visual permission preview
  - Conflict detection

### Risk 3: JWT Token Size Growth

- **Impact**: Medium
- **Probability**: Medium
- **Mitigation**:
  - Only include essential data in JWT
  - Use compression
  - Consider separate permissions endpoint
  - Monitor token size

### Risk 4: User Experience Complexity

- **Impact**: High
- **Probability**: Medium
- **Mitigation**:
  - User testing
  - Onboarding tour
  - Inline help
  - Video tutorials
  - Default templates

---

## References

### Internal Documentation

- [Permission System Guide](./PERMISSIONS_SYSTEM_GUIDE.md)
- [Permission System Quick Guide](./PERMISSION_SYSTEM_QUICK_GUIDE.md)
- Backend Models: `authentication/models.py`, `permissions/models.py`
- Frontend Hooks: `hooks/usePermissions.ts`

### External References

- Microsoft Business Central Role Centers: https://learn.microsoft.com/en-us/dynamics365/business-central/admin-role-center
- JWT Best Practices: https://tools.ietf.org/html/rfc8725
- WCAG AA Guidelines: https://www.w3.org/WAI/WCAG21/quickref/

---

## Appendix

### A. Sample Permission Set Configurations

```json
// SALES_FULL - Full sales access
{
  "code": "SALES_FULL",
  "name": "Sales - Full Access",
  "description": "Complete access to all sales features",
  "permission_lines": [
    { "object": "Sales Dashboard", "permissions": "RIMD" },
    { "object": "New Sale", "permissions": "RIMD" },
    { "object": "Sales History", "permissions": "RIMD" },
    { "object": "Sales Invoice", "permissions": "RIMD" }
  ]
}

// CUSTOMER_BASIC - Basic customer access
{
  "code": "CUSTOMER_BASIC",
  "name": "Customer - Basic Access",
  "description": "View and create customers only",
  "permission_lines": [
    { "object": "Customer Management", "permissions": "RI" }
  ]
}
```

### B. Sample User Group Configuration

```json
{
  "code": "SALES_TEAM",
  "name": "Sales Team",
  "description": "Front-line sales staff with full sales access",
  "default_profile": "Sales Manager",
  "permission_sets": ["SALES_FULL", "CUSTOMER_BASIC", "ITEMS_VIEW_ONLY"],
  "members": [1, 5, 12, 18]
}
```

### C. Sample Role Center Configuration

```json
{
  "code": "SALES_CENTER",
  "name": "Sales Role Center",
  "description": "Role center for sales team",
  "modules": ["sales", "customers", "items", "payments"],
  "features": {
    "sales": ["dashboard", "new_sale", "history", "invoices"],
    "customers": ["list", "create", "reports"]
  },
  "dashboard_widgets": ["sales_chart", "top_customers", "recent_invoices"]
}
```

---

**Document Status**: ✅ Complete and Ready for Implementation

**Next Steps**:

1. Review plan with team
2. Get stakeholder approval
3. Begin Phase 1 implementation
4. Set up weekly progress reviews
5. Create detailed task breakdown for first sprint

---

**Change Log**:

- 2025-10-31: Initial draft created
