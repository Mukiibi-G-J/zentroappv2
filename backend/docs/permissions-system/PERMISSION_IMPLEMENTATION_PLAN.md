# Permission System Implementation Plan for ZentroApp

## 📋 Executive Summary

This document outlines the complete implementation plan for integrating a Business Central-style permission system into ZentroApp. The plan addresses object management, multi-tenant architecture, and gradual rollout.

---

## 🎯 Phase 0: Understanding Current Setup

### What You Already Have:

1. ✅ **Objects Table** (`base/models.py` - `Objects` model)
2. ✅ **Object Population Script** (`base/management/commands/populate_objects_table.py`)
3. ✅ **Object ID Mapping** (TABLE_OBJECT_IDS dictionary with consistent IDs)
4. ✅ **Custom User Model** (`authentication/models.py` - `CustomUser`)
5. ✅ **Role System** (CustomUser has ManyToMany with Role)
6. ✅ **Multi-tenant Setup** (Django Tenants with Company model)

### What's Good:

- ✅ You already track all tables/objects
- ✅ Each object has a unique ID (2000-3300 range)
- ✅ You have object types (System, ThirdParty, Custom)
- ✅ Multi-tenant architecture is ready

---

## 🚀 Phase 1: Enhance Objects Model (Week 1)

### Goal: Transform existing Objects table into ApplicationObjects

### Step 1.1: Update Objects Model

**File**: `base/models.py`

```python
from django.db import models
from django.core.validators import MinValueValidator

class ObjectType(models.Model):
    """Categories of objects in the system"""
    name = models.CharField(max_length=100)  # Table, Page, Report, Codeunit
    code = models.CharField(max_length=20, unique=True)  # TABLE, PAGE, REPORT
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = "Object Type"
        verbose_name_plural = "Object Types"

    def __str__(self):
        return self.name

class Objects(models.Model):
    """Enhanced to work with permission system"""
    # Existing fields
    object_name = models.CharField(max_length=100)
    object_type = models.CharField(max_length=50, default="Table")  # KEEP THIS
    app_label = models.CharField(max_length=100)
    object_caption = models.CharField(max_length=250, blank=True, null=True)
    object_subtype = models.CharField(max_length=50, blank=True, null=True)
    object_id = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Unique numeric ID for the object"
    )

    # NEW FIELDS for permission system
    object_type_ref = models.ForeignKey(
        ObjectType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='objects',
        help_text="Link to ObjectType for permission system"
    )
    is_active = models.BooleanField(default=True)
    requires_permission = models.BooleanField(
        default=True,
        help_text="If False, object is accessible to all users"
    )
    related_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Full model path (e.g., 'customers.Customer')"
    )

    class Meta:
        ordering = ['object_type', 'object_id', 'object_name']
        verbose_name = "Application Object"
        verbose_name_plural = "Application Objects"
        unique_together = [['object_type', 'object_id']]

    def __str__(self):
        return f"{self.object_name} ({self.object_type} {self.object_id})"
```

### Step 1.2: Create Migration

```bash
# Run these commands:
cd zentro-backend
python manage.py makemigrations base --name add_permission_fields
python manage.py migrate base
```

### Step 1.3: Create ObjectTypes Setup Command

**File**: `base/management/commands/setup_object_types.py`

```python
from django.core.management.base import BaseCommand
from base.models import ObjectType

class Command(BaseCommand):
    help = "Create initial ObjectTypes for permission system"

    def handle(self, *args, **options):
        object_types = [
            {'name': 'Table', 'code': 'TABLE', 'sort_order': 1, 'description': 'Database tables'},
            {'name': 'Page', 'code': 'PAGE', 'sort_order': 2, 'description': 'UI pages and views'},
            {'name': 'Report', 'code': 'REPORT', 'sort_order': 3, 'description': 'Reports and analytics'},

        ]

        for obj_type_data in object_types:
            obj_type, created = ObjectType.objects.get_or_create(
                code=obj_type_data['code'],
                defaults=obj_type_data
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created ObjectType: {obj_type.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"ObjectType already exists: {obj_type.name}")
                )
```

**Run it**:

```bash
python manage.py setup_object_types
```

### Step 1.4: Update populate_objects_table.py

**Modify existing file**: `base/management/commands/populate_objects_table.py`

Add this after line 250:

```python
# Get or create object type reference
table_obj_type = ObjectType.objects.get(code='TABLE')

# Create or update Objects entry
obj, created = Objects.objects.update_or_create(
    object_name=formatted_name,
    defaults={
        "object_type": "Table",
        "object_type_ref": table_obj_type,  # NEW
        "app_label": app_label,
        "object_caption": verbose_name,
        "object_subtype": subtype,
        "object_id": object_id,
        "requires_permission": True,  # NEW
        "related_model": f"{app_label}.{formatted_name}",  # NEW
    },
)
```

---

## 🔐 Phase 2: Create Permission Models (Week 1-2)

### Step 2.1: Create Permission Models

**File**: `base/models.py` (add to existing file)

```python
class PermissionSet(models.Model):
    """Collection of permissions that can be assigned to roles/groups"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False,
        help_text="System permission sets cannot be deleted"
    )
    is_active = models.BooleanField(default=True)

    # Link to existing Role model (for compatibility)
    linked_role = models.ForeignKey(
        'authentication.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_sets',
        help_text="Link to existing role for backward compatibility"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Permission Set"
        verbose_name_plural = "Permission Sets"

    def __str__(self):
        return self.name

class PermissionSetLine(models.Model):
    """Individual permission rules within a permission set"""

    PERMISSION_CHOICES = [
        ('none', 'None'),
        ('yes', 'Yes'),
        ('indirect', 'Indirect'),
    ]

    EXECUTE_PERMISSION_CHOICES = [
        ('none', 'None'),
        ('yes', 'Yes'),
    ]

    permission_set = models.ForeignKey(
        PermissionSet,
        on_delete=models.CASCADE,
        related_name='permission_lines'
    )

    # Link to Objects table
    application_object = models.ForeignKey(
        Objects,
        on_delete=models.CASCADE,
        related_name='permissions',
        help_text="The object this permission applies to"
    )

    # Permission fields
    read_permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default='none'
    )
    insert_permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default='none'
    )
    modify_permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default='none'
    )
    delete_permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default='none'
    )
    execute_permission = models.CharField(
        max_length=10,
        choices=EXECUTE_PERMISSION_CHOICES,
        default='none'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['application_object__object_type', 'application_object__object_id']
        unique_together = ['permission_set', 'application_object']
        verbose_name = "Permission Set Line"
        verbose_name_plural = "Permission Set Lines"

    def __str__(self):
        return f"{self.permission_set.name} - {self.application_object.object_name}"
```

### Step 2.2: Run Migrations

```bash
python manage.py makemigrations base --name add_permission_models
python manage.py migrate base
```

---

## 🔗 Phase 3: Integrate with Existing Role System (Week 2)

### Step 3.1: Update CustomUser Model

**File**: `authentication/models.py`

Add this method to `CustomUser` class:

```python
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...

    def check_object_permission(self, object_id, permission_type):
        """
        Check if user has specific permission on an object

        Args:
            object_id: The numeric ID of the object (e.g., 2600 for Customer)
            permission_type: 'read', 'insert', 'modify', 'delete', or 'execute'

        Returns:
            bool: True if user has permission, False otherwise
        """
        from base.models import PermissionSetLine, Objects

        # Superusers always have permission
        if self.is_superuser:
            return True

        try:
            # Get the object
            app_object = Objects.objects.get(object_id=object_id)

            # If object doesn't require permission, allow all
            if not app_object.requires_permission:
                return True

            # Get all permission sets linked to user's roles
            permission_sets = PermissionSet.objects.filter(
                linked_role__in=self.roles.all()
            )

            # Check permission set lines
            permission_lines = PermissionSetLine.objects.filter(
                permission_set__in=permission_sets,
                application_object=app_object
            )

            for line in permission_lines:
                permission_value = getattr(line, f"{permission_type}_permission")
                if permission_value in ['yes', 'indirect']:
                    return True

            return False

        except Objects.DoesNotExist:
            # If object not found, deny by default
            return False

    def get_all_permissions(self):
        """Get all permissions for this user"""
        from base.models import PermissionSetLine

        if self.is_superuser:
            return {'superuser': True}

        permission_sets = PermissionSet.objects.filter(
            linked_role__in=self.roles.all()
        )

        permissions = {}
        permission_lines = PermissionSetLine.objects.filter(
            permission_set__in=permission_sets
        ).select_related('application_object')

        for line in permission_lines:
            key = f"obj_{line.application_object.object_id}"
            permissions[key] = {
                'object_id': line.application_object.object_id,
                'object_name': line.application_object.object_name,
                'read': line.read_permission,
                'insert': line.insert_permission,
                'modify': line.modify_permission,
                'delete': line.delete_permission,
                'execute': line.execute_permission,
            }

        return permissions
```

---

## 📊 Phase 4: Object Management Strategy (CRITICAL)

### Strategy: Automatic Object Discovery

**How it works:**

1. **Existing Objects**: Already tracked in your `populate_objects_table.py`
2. **New Tables**: Automatically added when you run `populate_objects_table`
3. **Pages/Reports**: Add manually as needed

### Step 4.1: Extend Object ID Ranges

**File**: `base/management/commands/populate_objects_table.py`

Update the `TABLE_OBJECT_IDS` dictionary:

```python
TABLE_OBJECT_IDS = {
    # Keep all existing IDs (2000-3399)

    # RESERVE RANGES for future modules:
    # Hotel Management: 3400-3499 (you already have hotel_management module)
    # Production: 3500-3599 (you already have production module)
    # Resources: 3600-3699 (you already have resources module)
    # Future Module 1: 3700-3799
    # Future Module 2: 3800-3899
    # ... up to 9999

    # For new tables not in the dictionary, use auto-increment from 5000
}
```

### Step 4.2: Create Page/Report Registration System

**File**: `base/management/commands/register_pages.py`

```python
from django.core.management.base import BaseCommand
from base.models import Objects, ObjectType

# Define your pages/reports with their IDs
PAGES = {
    # Customer Pages (10000-10099)
    "customer_list": {
        "id": 10001,
        "name": "Customer List",
        "caption": "Customer List Page",
        "app_label": "customers",
        "route": "/customers",
    },
    "customer_detail": {
        "id": 10002,
        "name": "Customer Detail",
        "caption": "Customer Detail Page",
        "app_label": "customers",
        "route": "/customers/:id",
    },

    # Sales Pages (10100-10199)
    "sales_order_list": {
        "id": 10101,
        "name": "Sales Order List",
        "caption": "Sales Orders",
        "app_label": "sales",
        "route": "/sales/orders",
    },

    # Reports (20000-20999)
    "sales_report": {
        "id": 20001,
        "name": "Sales Report",
        "caption": "Sales Analysis Report",
        "app_label": "sales",
        "type": "REPORT",
    },
}

class Command(BaseCommand):
    help = "Register pages and reports for permission system"

    def handle(self, *args, **options):
        page_type = ObjectType.objects.get(code='PAGE')
        report_type = ObjectType.objects.get(code='REPORT')

        for code, data in PAGES.items():
            obj_type = report_type if data.get('type') == 'REPORT' else page_type

            obj, created = Objects.objects.update_or_create(
                object_id=data['id'],
                defaults={
                    'object_name': data['name'],
                    'object_type': obj_type.name,
                    'object_type_ref': obj_type,
                    'object_caption': data['caption'],
                    'app_label': data['app_label'],
                    'object_subtype': 'Custom',
                    'requires_permission': True,
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created {obj_type.name}: {data['name']}")
                )
```

### Step 4.3: When You Add New Features

**Process**:

1. **New Table**:

   - Add to `TABLE_OBJECT_IDS` in `populate_objects_table.py`
   - Run `python manage.py populate_objects_table`

2. **New Page/View**:

   - Add to `PAGES` dictionary in `register_pages.py`
   - Run `python manage.py register_pages`

3. **New Report**:
   - Add to `PAGES` dictionary with `type: "REPORT"`
   - Run `python manage.py register_pages`

### Step 4.4: Automatic Object Discovery Hook

**File**: `base/signals.py` (create new file)

```python
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.management import call_command

@receiver(post_migrate)
def auto_populate_objects(sender, **kwargs):
    """Automatically populate objects after migrations"""
    if sender.name == 'base':
        try:
            call_command('populate_objects_table')
            print("✓ Objects table automatically populated")
        except Exception as e:
            print(f"✗ Could not auto-populate objects: {e}")
```

**File**: `base/apps.py`

```python
from django.apps import AppConfig

class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'base'

    def ready(self):
        import base.signals  # Import signals
```

---

## 🎨 Phase 5: Admin Interface (Week 2-3)

### Step 5.1: Create Permission Admin

**File**: `base/admin.py`

```python
from django.contrib import admin
from django.db.models import Count
from .models import ObjectType, Objects, PermissionSet, PermissionSetLine

@admin.register(ObjectType)
class ObjectTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'sort_order', 'object_count']
    list_editable = ['sort_order']
    search_fields = ['name', 'code']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(obj_count=Count('objects'))

    def object_count(self, obj):
        return obj.obj_count
    object_count.short_description = 'Objects'
    object_count.admin_order_field = 'obj_count'

@admin.register(Objects)
class ObjectsAdmin(admin.ModelAdmin):
    list_display = [
        'object_id',
        'object_name',
        'object_type',
        'app_label',
        'object_subtype',
        'requires_permission',
        'is_active'
    ]
    list_filter = ['object_type', 'object_subtype', 'requires_permission', 'is_active']
    search_fields = ['object_name', 'object_caption', 'app_label']
    list_editable = ['requires_permission', 'is_active']
    ordering = ['object_type', 'object_id']

    fieldsets = (
        ('Basic Information', {
            'fields': ('object_id', 'object_name', 'object_caption')
        }),
        ('Classification', {
            'fields': ('object_type', 'object_type_ref', 'object_subtype', 'app_label')
        }),
        ('Permission Settings', {
            'fields': ('requires_permission', 'is_active')
        }),
        ('Technical', {
            'fields': ('related_model',),
            'classes': ('collapse',)
        }),
    )

class PermissionSetLineInline(admin.TabularInline):
    model = PermissionSetLine
    extra = 1
    fields = [
        'application_object',
        'read_permission',
        'insert_permission',
        'modify_permission',
        'delete_permission',
        'execute_permission'
    ]
    autocomplete_fields = ['application_object']

@admin.register(PermissionSet)
class PermissionSetAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'linked_role', 'is_system', 'is_active', 'line_count']
    list_filter = ['is_system', 'is_active', 'linked_role']
    search_fields = ['name', 'code', 'description']
    inlines = [PermissionSetLineInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(lines_count=Count('permission_lines'))

    def line_count(self, obj):
        return obj.lines_count
    line_count.short_description = 'Permission Lines'
    line_count.admin_order_field = 'lines_count'

@admin.register(PermissionSetLine)
class PermissionSetLineAdmin(admin.ModelAdmin):
    list_display = [
        'permission_set',
        'application_object',
        'read_permission',
        'insert_permission',
        'modify_permission',
        'delete_permission',
        'execute_permission'
    ]
    list_filter = [
        'permission_set',
        'read_permission',
        'insert_permission',
        'modify_permission',
        'delete_permission'
    ]
    search_fields = [
        'permission_set__name',
        'application_object__object_name'
    ]
    autocomplete_fields = ['permission_set', 'application_object']
```

---

## 📦 Phase 6: Create Default Permission Sets (Week 3)

### Step 6.1: Create Setup Command

**File**: `base/management/commands/setup_default_permissions.py`

```python
from django.core.management.base import BaseCommand
from base.models import PermissionSet, PermissionSetLine, Objects
from authentication.models import Role

class Command(BaseCommand):
    help = "Create default permission sets for common roles"

    def handle(self, *args, **options):
        # Get or create roles
        admin_role, _ = Role.objects.get_or_create(
            name="Admin",
            defaults={'authority': 100}
        )
        manager_role, _ = Role.objects.get_or_create(
            name="Manager",
            defaults={'authority': 80}
        )
        cashier_role, _ = Role.objects.get_or_create(
            name="Cashier",
            defaults={'authority': 40}
        )

        # Create Permission Sets
        admin_perm, created = PermissionSet.objects.get_or_create(
            code="ADMIN_FULL",
            defaults={
                'name': "Admin - Full Access",
                'description': "Full access to all objects",
                'is_system': True,
                'linked_role': admin_role
            }
        )

        if created:
            # Give admin full access to all objects
            for obj in Objects.objects.filter(requires_permission=True):
                PermissionSetLine.objects.create(
                    permission_set=admin_perm,
                    application_object=obj,
                    read_permission='yes',
                    insert_permission='yes',
                    modify_permission='yes',
                    delete_permission='yes',
                    execute_permission='yes'
                )
            self.stdout.write(self.style.SUCCESS("Created ADMIN_FULL permission set"))

        # Create Cashier Permission Set
        cashier_perm, created = PermissionSet.objects.get_or_create(
            code="CASHIER",
            defaults={
                'name': "Cashier",
                'description': "POS and basic customer access",
                'is_system': True,
                'linked_role': cashier_role
            }
        )

        if created:
            # Define cashier permissions
            cashier_objects = {
                2600: {'read': 'yes', 'insert': 'yes', 'modify': 'yes', 'delete': 'none'},  # Customer
                2500: {'read': 'yes', 'insert': 'none', 'modify': 'none', 'delete': 'none'},  # Item
                2701: {'read': 'yes', 'insert': 'yes', 'modify': 'yes', 'delete': 'none'},  # Sale
                2702: {'read': 'yes', 'insert': 'yes', 'modify': 'yes', 'delete': 'none'},  # SaleLine
            }

            for obj_id, perms in cashier_objects.items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)
                    PermissionSetLine.objects.create(
                        permission_set=cashier_perm,
                        application_object=obj,
                        read_permission=perms.get('read', 'none'),
                        insert_permission=perms.get('insert', 'none'),
                        modify_permission=perms.get('modify', 'none'),
                        delete_permission=perms.get('delete', 'none'),
                        execute_permission='none'
                    )
                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"Object {obj_id} not found")
                    )

            self.stdout.write(self.style.SUCCESS("Created CASHIER permission set"))

        self.stdout.write(
            self.style.SUCCESS("Default permission sets created successfully!")
        )
```

**Run it**:

```bash
python manage.py setup_default_permissions
```

---

## 🔌 Phase 7: API Integration (Week 3-4)

### Step 7.1: Create Serializers

**File**: `base/serializers.py` (create new file)

```python
from rest_framework import serializers
from .models import ObjectType, Objects, PermissionSet, PermissionSetLine

class ObjectTypeSerializer(serializers.ModelSerializer):
    object_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ObjectType
        fields = '__all__'

class ObjectsSerializer(serializers.ModelSerializer):
    object_type_name = serializers.CharField(source='object_type_ref.name', read_only=True)

    class Meta:
        model = Objects
        fields = '__all__'

class PermissionSetLineSerializer(serializers.ModelSerializer):
    object_name = serializers.CharField(source='application_object.object_name', read_only=True)
    object_id = serializers.IntegerField(source='application_object.object_id', read_only=True)

    class Meta:
        model = PermissionSetLine
        fields = '__all__'

class PermissionSetSerializer(serializers.ModelSerializer):
    permission_lines = PermissionSetLineSerializer(many=True, read_only=True)
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = PermissionSet
        fields = '__all__'

    def get_line_count(self, obj):
        return obj.permission_lines.count()

class UserPermissionsSerializer(serializers.Serializer):
    """Serializer for user's complete permission structure"""
    object_id = serializers.IntegerField()
    object_name = serializers.CharField()
    read = serializers.CharField()
    insert = serializers.CharField()
    modify = serializers.CharField()
    delete = serializers.CharField()
    execute = serializers.CharField()
```

### Step 7.2: Create Views

**File**: `base/views.py`

```python
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count
from .models import ObjectType, Objects, PermissionSet, PermissionSetLine
from .serializers import (
    ObjectTypeSerializer, ObjectsSerializer,
    PermissionSetSerializer, PermissionSetLineSerializer
)

class ObjectTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ObjectType.objects.annotate(object_count=Count('objects'))
    serializer_class = ObjectTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class ObjectsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Objects.objects.select_related('object_type_ref')
    serializer_class = ObjectsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['object_type', 'app_label', 'requires_permission']
    search_fields = ['object_name', 'object_caption']

class PermissionSetViewSet(viewsets.ModelViewSet):
    queryset = PermissionSet.objects.prefetch_related('permission_lines')
    serializer_class = PermissionSetSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def add_permission_line(self, request, pk=None):
        """Add a permission line to this permission set"""
        permission_set = self.get_object()
        serializer = PermissionSetLineSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(permission_set=permission_set)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_permissions(request):
    """Get all permissions for the current user"""
    user = request.user
    permissions = user.get_all_permissions()
    return Response(permissions)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def check_permission(request):
    """Check if user has specific permission"""
    object_id = request.data.get('object_id')
    permission_type = request.data.get('permission_type')

    if not object_id or not permission_type:
        return Response(
            {'error': 'object_id and permission_type are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    has_permission = request.user.check_object_permission(
        object_id, permission_type
    )

    return Response({
        'has_permission': has_permission,
        'object_id': object_id,
        'permission_type': permission_type
    })
```

### Step 7.3: Create URLs

**File**: `base/urls.py`

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'object-types', views.ObjectTypeViewSet)
router.register(r'objects', views.ObjectsViewSet)
router.register(r'permission-sets', views.PermissionSetViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('user-permissions/', views.get_user_permissions, name='user-permissions'),
    path('check-permission/', views.check_permission, name='check-permission'),
]
```

**Update main urls** (`core/urls.py` or similar):

```python
urlpatterns = [
    # ... existing urls ...
    path('api/permissions/', include('base.urls')),
]
```

---

## 🎯 Phase 8: Frontend Integration (Week 4-5)

### Step 8.1: Create Permission Context

**File**: `zentro-frontend/src/contexts/PermissionContext.tsx`

```typescript
import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "@/services/api";

interface Permission {
  object_id: number;
  object_name: string;
  read: string;
  insert: string;
  modify: string;
  delete: string;
  execute: string;
}

interface PermissionContextType {
  permissions: Record<string, Permission>;
  loading: boolean;
  checkPermission: (objectId: number, permissionType: string) => boolean;
  reloadPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType | undefined>(
  undefined
);

export const PermissionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [permissions, setPermissions] = useState<Record<string, Permission>>(
    {}
  );
  const [loading, setLoading] = useState(true);

  const loadPermissions = async () => {
    try {
      setLoading(true);
      const response = await api.get("/permissions/user-permissions/");

      // Handle superuser case
      if (response.data.superuser) {
        // Superuser has all permissions
        setPermissions({ superuser: true } as any);
      } else {
        setPermissions(response.data);
      }
    } catch (error) {
      console.error("Error loading permissions:", error);
      setPermissions({});
    } finally {
      setLoading(false);
    }
  };

  const checkPermission = (
    objectId: number,
    permissionType: string
  ): boolean => {
    // Superuser check
    if ((permissions as any).superuser) return true;

    const key = `obj_${objectId}`;
    const objectPerms = permissions[key];

    if (!objectPerms) return false;

    const permValue = objectPerms[permissionType as keyof Permission];

    if (permissionType === "execute") {
      return permValue === "yes";
    }

    return ["yes", "indirect"].includes(permValue);
  };

  useEffect(() => {
    loadPermissions();
  }, []);

  return (
    <PermissionContext.Provider
      value={{
        permissions,
        loading,
        checkPermission,
        reloadPermissions: loadPermissions,
      }}
    >
      {children}
    </PermissionContext.Provider>
  );
};

export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error("usePermissions must be used within PermissionProvider");
  }
  return context;
};
```

### Step 8.2: Create Permission Hook

**File**: `zentro-frontend/src/hooks/useObjectPermission.ts`

```typescript
import { usePermissions } from "@/contexts/PermissionContext";

// Object ID constants (from your TABLE_OBJECT_IDS)
export const OBJECTS = {
  // Customers
  CUSTOMER: 2600,
  CUSTOMER_GROUP: 2601,

  // Items
  ITEM: 2500,
  ITEM_CATEGORY: 2501,

  // Sales
  SALE: 2701,
  SALE_LINE: 2702,

  // Pages (when you add them)
  CUSTOMER_LIST_PAGE: 10001,
  SALES_ORDER_PAGE: 10101,

  // Add more as needed
} as const;

export const useObjectPermission = (objectId: number) => {
  const { checkPermission, loading } = usePermissions();

  return {
    canRead: checkPermission(objectId, "read"),
    canInsert: checkPermission(objectId, "insert"),
    canModify: checkPermission(objectId, "modify"),
    canDelete: checkPermission(objectId, "delete"),
    canExecute: checkPermission(objectId, "execute"),
    loading,
  };
};
```

### Step 8.3: Use in Components

**Example**: Customer list page

```typescript
import { useObjectPermission, OBJECTS } from "@/hooks/useObjectPermission";

const CustomerList = () => {
  const { canRead, canInsert, canModify, canDelete } = useObjectPermission(
    OBJECTS.CUSTOMER
  );

  if (!canRead) {
    return <div>You don't have permission to view customers.</div>;
  }

  return (
    <div>
      <h1>Customers</h1>

      {canInsert && <button onClick={handleAddNew}>Add New Customer</button>}

      <table>
        {/* Customer list */}
        <tbody>
          {customers.map((customer) => (
            <tr key={customer.id}>
              <td>{customer.name}</td>
              <td>
                {canModify && <button>Edit</button>}
                {canDelete && <button>Delete</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

## ✅ Phase 9: Testing & Validation (Week 5-6)

### Step 9.1: Test Checklist

- [ ] Can create permission sets via admin
- [ ] Can add permission lines via admin
- [ ] Permission sets link to roles correctly
- [ ] User permissions API returns correct data
- [ ] Frontend permission checks work
- [ ] Superuser has all permissions
- [ ] Users without permissions are blocked
- [ ] New objects are automatically discovered
- [ ] Multi-tenant isolation works (permissions per company)

### Step 9.2: Create Test Users

```bash
# In Django shell
python manage.py shell

from authentication.models import CustomUser, Role
from base.models import PermissionSet

# Create test cashier
cashier_role = Role.objects.get(name="Cashier")
cashier_user = CustomUser.objects.create_user(
    email="cashier@test.com",
    password="test123",
    username="testcashier"
)
cashier_user.roles.add(cashier_role)

# Test permissions
print(cashier_user.check_object_permission(2600, 'read'))  # Should be True
print(cashier_user.check_object_permission(2600, 'delete'))  # Should be False
```

---

## 📈 Phase 10: Gradual Rollout (Week 6+)

### Rollout Strategy:

1. **Week 6**: Start with one module (e.g., Customers)

   - Add permission checks to customer views
   - Test with different user roles
   - Fix any issues

2. **Week 7**: Add second module (e.g., Sales)

   - Apply learnings from first module
   - Create more granular permissions

3. **Week 8**: Expand to 3-4 more modules

4. **Week 9+**: Continue until all modules covered

---

## 🔄 Maintenance Process

### When You Add New Features:

```bash
# 1. Create your new model/view
# 2. Add to object registry
python manage.py populate_objects_table  # For tables
python manage.py register_pages  # For pages

# 3. Update default permission sets if needed
python manage.py setup_default_permissions --update

# 4. Test permissions work
```

### Monthly Tasks:

- Review permission sets
- Audit who has what access
- Remove unused objects
- Update documentation

---

## 📚 Summary & Next Steps

### Implementation Order:

1. ✅ **Week 1**: Enhance Objects model, create ObjectTypes
2. ✅ **Week 1-2**: Create permission models & migrations
3. ✅ **Week 2**: Integrate with existing roles
4. ✅ **Week 2-3**: Build admin interface
5. ✅ **Week 3**: Create default permission sets
6. ✅ **Week 3-4**: Build API endpoints
7. ✅ **Week 4-5**: Frontend integration
8. ✅ **Week 5-6**: Testing & validation
9. ✅ **Week 6+**: Gradual rollout to all modules

### Key Files to Create/Modify:

**New Files**:

- `base/management/commands/setup_object_types.py`
- `base/management/commands/register_pages.py`
- `base/management/commands/setup_default_permissions.py`
- `base/serializers.py`
- `base/signals.py`
- `zentro-frontend/src/contexts/PermissionContext.tsx`
- `zentro-frontend/src/hooks/useObjectPermission.ts`

**Modified Files**:

- `base/models.py` (add ObjectType, PermissionSet, PermissionSetLine)
- `base/admin.py` (add admin classes)
- `base/views.py` (add API views)
- `base/urls.py` (add API routes)
- `base/management/commands/populate_objects_table.py` (link to ObjectType)
- `authentication/models.py` (add permission methods to CustomUser)

---

## 🎯 Success Criteria

- ✅ All objects automatically tracked
- ✅ Permission system integrated with existing roles
- ✅ Admin can easily manage permissions
- ✅ Frontend respects permissions
- ✅ Multi-tenant isolation maintained
- ✅ Easy to add new objects/permissions
- ✅ Performance is good (< 100ms permission checks)

---

**Ready to start? Begin with Phase 1!** 🚀
