# Resources & Production BOM - Implementation Tasks

This document outlines all tasks needed to implement the Resources and Production Bill of Materials system for service-based businesses.

---

## Phase 1: Backend Foundation (Tasks 1-10)

### Task 1: Create Resources Django App and Models ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** None

**What to do:**

- Create new Django app: `zentro-backend/resources/`
- Implement `Resource` model with fields:
  - `company` (ForeignKey to Company)
  - `code` (CharField, unique) - auto-generated
  - `name` (CharField, max_length=100)
  - `resource_type` (CharField, choices: 'person', 'equipment', 'space')
  - `base_unit` (CharField, default='HOUR')
  - `cost_rate` (DecimalField) - what business pays
  - `charge_rate` (DecimalField) - what customer pays
  - `is_active` (BooleanField, default=True)
  - `description` (TextField, blank=True)
  - `photo` (ImageField, blank=True, null=True)
- Inherit from `BaseModel` for `created_at`/`updated_at`
- Add proper `Meta` class with verbose names and ordering
- Register app in `settings.py` INSTALLED_APPS

**Test:**

- Create and run migrations successfully
- Test in Django admin by creating test resources
- Verify all fields save correctly and uniqueness constraints work

---

### Task 2: Setup Resource Number Series Integration ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Task 1

**What to do:**

- Add number series configuration in `settings` app
- Create number series entry with format: `RES-{company_code}-{number}`
- Implement auto-generation logic in Resource model's `save()` method
- Follow existing patterns from `Items` and `Company` models
- Ensure codes are unique per company

**Test:**

- Create multiple resources and verify codes auto-generate correctly
- Test code uniqueness within same company
- Verify number series increments properly

---

### Task 3: Create Resource Admin Interface ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Tasks 1, 2

**What to do:**

- Create `ResourceAdmin` class in `resources/admin.py`
- Configure `list_display`: code, name, resource_type, cost_rate, charge_rate, is_active
- Add `list_filter` for resource_type and is_active
- Add `search_fields` for code and name
- Make `is_active` editable inline
- Add proper fieldsets for organization
- Include company field handling for multi-tenancy

**Test:**

- Access Django admin and test full CRUD operations
- Verify filters work correctly
- Test search functionality
- Create, edit, and delete resources successfully

---

### Task 4: Create Production Django App and ProductionBOM Model ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Tasks 1, 2, 3

**What to do:**

- Create new Django app: `zentro-backend/production/`
- Implement `ProductionBOM` model with fields:
  - `company` (ForeignKey to Company)
  - `bom_code` (CharField, unique) - auto-generated
  - `name` (CharField, max_length=100)
  - `service_item` (OneToOneField to Item model)
  - `is_active` (BooleanField, default=True)
  - `notes` (TextField, blank=True)
- Inherit from `BaseModel`
- Add validation to ensure `service_item` is of type 'service'
- Add methods:
  - `calculate_total_cost()`
  - `calculate_profit_margin()`
  - `get_resource_requirements()`
  - `get_inventory_requirements()`
- Register app in `settings.py`

**Test:**

- Create and run migrations
- Test in Django shell by creating ProductionBOM instances
- Verify OneToOne relationship with Item works correctly
- Test validation rules

---

### Task 5: Setup ProductionBOM Number Series Integration ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Task 4

**What to do:**

- Add number series configuration in `settings` app
- Create number series entry with format: `BOM-{company_code}-{number}`
- Implement auto-generation logic in ProductionBOM model's `save()` method
- Follow existing patterns from Resources
- Ensure codes are unique per company

**Test:**

- Create multiple BOMs and verify codes auto-generate correctly
- Test code uniqueness
- Verify number series increments properly

---

### Task 6: Create BOMLine Model ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Task 4

**What to do:**

- Create `BOMLine` model with fields:
  - `bom` (ForeignKey to ProductionBOM, related_name='lines')
  - `line_number` (IntegerField)
  - `line_type` (CharField, choices: 'resource', 'inventory')
  - `resource` (ForeignKey to Resource, null=True, blank=True)
  - `resource_quantity` (DecimalField, default=0)
  - `inventory_item` (ForeignKey to Item, null=True, blank=True)
  - `inventory_quantity` (DecimalField, default=0)
  - `unit_cost` (DecimalField) - auto-calculated
  - `total_cost` (DecimalField) - auto-calculated
  - `notes` (TextField, blank=True)
- Implement `save()` method to auto-calculate unit_cost and total_cost
- Add validation: either resource OR inventory is set, not both
- Inherit from `BaseModel`

**Test:**

- Create BOM lines in Django shell
- Verify cost calculations work correctly
- Test validation rules (resource XOR inventory)
- Verify relationships work properly

---

### Task 7: Create Production BOM Admin with Inline BOMLines ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Tasks 4, 5, 6

**What to do:**

- Create `BOMLineInline` (TabularInline) for editing BOM lines
- Configure inline fields: line_number, line_type, resource, resource_quantity, inventory_item, inventory_quantity, unit_cost (readonly), total_cost (readonly)
- Create `ProductionBOMAdmin` with:
  - `list_display`: bom_code, name, service_item, total_cost_display, profit_margin_display, is_active
  - `list_filter` for is_active
  - `search_fields` for bom_code, name, service_item\_\_name
  - Include `BOMLineInline`
- Add custom methods to display calculated costs and profit margins
- Use `select_related` for performance

**Test:**

- Test full BOM creation with multiple lines in admin
- Verify inline editing works smoothly
- Test cost calculations display correctly
- Create complex BOMs with both resource and inventory lines

---

### Task 8: Implement ProductionBOM Cost Calculation Methods ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Task 6

**What to do:**

- Implement `calculate_total_cost()` method:
  - Iterate through all BOM lines
  - Sum up total_cost from each line
- Implement `calculate_profit_margin()` method:
  - Get service_item.base_price
  - Calculate (price - total_cost) / price \* 100
- Implement `get_resource_requirements()` method:
  - Return list of resources with quantities
- Implement `get_inventory_requirements()` method:
  - Return list of inventory items with quantities
- Add property decorators for easy access
- Handle edge cases (no lines, zero price, etc.)

**Test:**

- Create test BOMs with known costs
- Verify calculations match manual calculations
- Test edge cases (empty BOM, zero price, negative values)
- Test performance with BOMs containing many lines

---

### Task 9: Extend SaleLine Model for Service Sales ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Tasks 1, 4, 6

**What to do:**

- Add new fields to `SaleLine` model in `sales/models.py`:
  - `line_type` (CharField, choices: 'product', 'service', default='product')
  - `assigned_resource` (ForeignKey to Resource, null=True, blank=True)
  - `service_duration` (DecimalField, null=True, blank=True)
  - `unit_cost` (DecimalField, default=0)
  - `total_cost` (DecimalField, default=0)
- Create migration for these new fields
- Update existing code for backward compatibility
- Update model's `save()` method to calculate costs for service sales

**Test:**

- Run migrations on test database
- Verify existing sales data remains intact
- Create test service sales in Django shell
- Verify new fields save correctly

---

### Task 10: Implement BOM Processing Logic for Service Sales ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Tasks 8, 9

**What to do:**

- Create utility function `process_service_sale(sale_line)` in `production/utils.py`
- When a service sale line is saved:
  1. Check if service item has a production_bom
  2. If yes, iterate through BOM lines
  3. For inventory lines: deduct inventory_quantity \* sale_quantity from item's quantity_on_hand
  4. For resource lines: log resource utilization
  5. Calculate and set unit_cost and total_cost on sale_line
- Handle edge cases: insufficient inventory, inactive resources, missing BOM
- Implement within database transaction for data integrity

**Test:**

- Create test service sale with BOM
- Verify inventory is deducted correctly
- Test with insufficient inventory (should fail gracefully)
- Test transaction rollback on errors
- Verify cost calculations are accurate

---

## Phase 2: Backend APIs (Tasks 11-13)

### Task 11: Create Resources API Endpoints

**Status:** Pending  
**Dependencies:** Task 3  
**Priority:** Medium

**What to do:**

- Create `ResourceSerializer` in `resources/serializers.py` with camelCase field names
- Create API views in `resources/views.py`:
  - `list_resources` (GET with filtering, search, pagination)
  - `create_resource` (POST)
  - `get_resource` (GET)
  - `update_resource` (PUT)
  - `delete_resource` (DELETE)
  - `get_available_resources` (GET - active resources only for POS)
- Add URL patterns in `resources/urls.py` with prefix '/api/resources/'
- Ensure proper company isolation and permissions
- Follow existing patterns from `items` app

**Test:**

- Test all endpoints with Postman/curl
- Verify CRUD operations work correctly
- Test filtering and search
- Verify camelCase response format
- Test permissions and company isolation

---

### Task 12: Create Production BOM API Endpoints

**Status:** Pending  
**Dependencies:** Tasks 7, 8  
**Priority:** Medium

**What to do:**

- Create `ProductionBOMSerializer` and `BOMLineSerializer` in `production/serializers.py`
- Include nested BOMLine serialization in BOM detail view
- Create API views:
  - `list_boms` (GET)
  - `create_bom` (POST)
  - `get_bom_detail` (GET with nested lines)
  - `update_bom` (PUT)
  - `delete_bom` (DELETE)
  - `get_cost_analysis` (GET - detailed cost breakdown)
  - `bulk_create_boms` (POST)
- Create BOM line endpoints: create_line, update_line, delete_line
- Add URL patterns in `production/urls.py`

**Test:**

- Test all endpoints thoroughly
- Verify nested BOM line serialization
- Test bulk operations
- Verify cost calculations in API responses
- Test validation rules (resource XOR inventory)

---

### Task 13: Create Sales Integration API for Service Sales

**Status:** Pending  
**Dependencies:** Tasks 10, 11  
**Priority:** Medium

**What to do:**

- Extend existing sales API in `sales/views.py`
- Add endpoint `process_service_sale` (POST)
- Add endpoint `get_service_profitability` (GET) for reporting
- Update existing sale creation endpoint to handle service line types
- Ensure BOM processing is called automatically
- Add proper error handling for insufficient inventory, inactive resources
- Return detailed cost breakdown in response

**Test:**

- Test service sale creation via API
- Verify BOM processing happens automatically
- Test with various scenarios (with/without BOM, sufficient/insufficient inventory)
- Verify response includes cost details

---

## Phase 3: Frontend - Resources (Tasks 14-15)

### Task 14: Create Resources Frontend - Listing Page

**Status:** Pending  
**Dependencies:** Task 11  
**Priority:** Medium

**What to do:**

- Create `Resources.tsx` in `zentro-frontend/src/views/resources/`
- Use `BaseTable` component following project patterns
- Implement columns: code, name, resourceType, costRate, chargeRate, isActive
- Add search functionality
- Add filters for resourceType and isActive
- Implement pagination
- Add Create, Edit, Delete actions
- Follow existing patterns from Items listing page
- Use Tailwind CSS for styling

**Test:**

- Test listing loads correctly
- Verify search and filters work
- Test pagination
- Verify all actions work (create, edit, delete)
- Test responsive design on mobile

---

### Task 15: Create Resources Frontend - Create/Edit Modal

**Status:** Pending  
**Dependencies:** Task 14  
**Priority:** Medium

**What to do:**

- Create `ResourceModal.tsx` in `zentro-frontend/src/views/resources/components/`
- Build form with fields:
  - name (text input)
  - resourceType (dropdown)
  - baseUnit (dropdown)
  - costRate (number input)
  - chargeRate (number input)
  - description (textarea)
  - photo (file upload)
  - isActive (toggle)
- Implement validation:
  - Required fields
  - costRate >= 0
  - chargeRate >= costRate
- Handle create and edit modes
- Show loading state during API calls
- Display success/error messages
- Auto-refresh listing on success

**Test:**

- Test creating new resources
- Test editing existing resources
- Verify validation works correctly
- Test file upload for photo
- Verify form resets properly

---

## Phase 4: Frontend - Production BOM (Tasks 16-17)

### Task 16: Create Production BOM Frontend - Listing Page

**Status:** Pending  
**Dependencies:** Task 12  
**Priority:** Medium

**What to do:**

- Create `ProductionBOM.tsx` in `zentro-frontend/src/views/production/`
- Use `BaseTable` component
- Implement columns: bomCode, name, serviceItem, totalCost, profitMargin (with color coding), lineCount, isActive
- Add search functionality
- Add filter for isActive
- Add actions: Create, Edit, View Details, Delete
- Show cost analysis on hover or expansion
- Link to service item details

**Test:**

- Test listing loads with calculated costs
- Verify profit margin color coding works
- Test all actions
- Verify performance with many BOMs

---

### Task 17: Create Production BOM Frontend - BOM Builder/Editor

**Status:** Pending  
**Dependencies:** Task 16  
**Priority:** Medium

**What to do:**

- Create `BOMBuilder.tsx` component
- Step 1: Select service item (from items where type='service')
- Step 2: Add BOM lines with inline editor:
  - Line type selector (resource/inventory)
  - Resource/inventory selector (conditional based on type)
  - Quantity input
  - Auto-displayed unit cost and total cost
- Step 3: Review with total cost summary and profit margin calculation
- Add/remove lines dynamically
- Real-time cost calculations
- Handle edit mode for existing BOMs

**Test:**

- Test creating new BOMs with multiple lines
- Test editing existing BOMs
- Verify real-time calculations work
- Test adding/removing lines
- Test with both resource and inventory lines

---

## Phase 5: Frontend - POS Integration (Tasks 18-20)

### Task 18: Integrate Service Sales into POS - Item Selection

**Status:** Pending  
**Dependencies:** Tasks 13, 14  
**Priority:** Medium

**What to do:**

- Update `ItemSelectionModal.tsx` in `zentro-frontend/src/views/sales/components/`
- Add service indicator badge to service items
- Show BOM icon if service has production_bom
- Display estimated cost vs. selling price on hover
- Filter option to show only services or only products
- When service is selected, open ResourceAssignmentModal

**Test:**

- Test selecting both product and service items
- Verify service indicators display correctly
- Test filtering
- Verify resource modal opens for services

---

### Task 19: Create Resource Assignment Modal for POS

**Status:** Pending  
**Dependencies:** Task 18  
**Priority:** Medium

**What to do:**

- Create `ResourceAssignmentModal.tsx`
- Display service details and BOM information
- Show list of available resources filtered by type
- Allow resource selection (dropdown or cards)
- Show resource cost rate and estimated profit
- Optional: duration adjustment
- Add to cart button with selected resource
- Show warning if BOM requires inventory that's out of stock

**Test:**

- Test resource selection for various services
- Verify available resources load correctly
- Test adding service to cart with resource
- Test inventory validation

---

### Task 20: Update POS Sales Processing for Services ⭐ HIGH PRIORITY

**Status:** Pending  
**Dependencies:** Task 19

**What to do:**

- Update `SalesInvoice.tsx` and sales processing logic
- When sale is completed, process service sales through API
- Display service sales with resource information in sale line items
- Show cost vs. revenue for service sales (for authorized users)
- Handle BOM processing errors gracefully
- Update sales receipt to show service provider information
- Refresh inventory after successful service sale

**Test:**

- Complete end-to-end service sale in POS
- Verify inventory deducts correctly
- Test with insufficient inventory (should fail gracefully)
- Verify receipt shows resource info
- Test cost tracking

---

## Phase 6: Reporting (Tasks 21-22)

### Task 21: Create Service Profitability Dashboard

**Status:** Pending  
**Dependencies:** Task 20  
**Priority:** Low

**What to do:**

- Create `ServiceProfitability.tsx` in `zentro-frontend/src/views/reports/`
- Display charts:
  - Profit margin by service
  - Revenue vs cost comparison
  - Top profitable services
  - Low margin services
- Add filters: date range, service category, specific services
- Show summary cards: total service revenue, total service cost, average profit margin, number of services sold
- Add export to CSV functionality
- Use chart library (recharts or similar)

**Test:**

- Test with various date ranges
- Verify calculations are accurate
- Test filters work correctly
- Test export functionality
- Verify charts render properly

---

### Task 22: Create Resource Utilization Report

**Status:** Pending  
**Dependencies:** Task 20  
**Priority:** Low

**What to do:**

- Create `ResourceUtilization.tsx` in `zentro-frontend/src/views/reports/`
- Display metrics per resource:
  - Total hours/units used
  - Number of services performed
  - Revenue generated
  - Cost incurred
  - Profit contribution
- Add filters: date range, resource type, specific resources
- Show utilization rate (actual vs. available hours)
- Add comparison charts between resources
- Include export functionality

**Test:**

- Test with multiple resources
- Verify metrics calculate correctly
- Test filters and date ranges
- Verify comparisons work
- Test export

---

## Phase 7: Performance & Testing (Tasks 23-25)

### Task 23: Add Database Indexes for Performance

**Status:** Pending  
**Dependencies:** Tasks 6, 9  
**Priority:** Medium

**What to do:**

- Create migration to add indexes:
  - `resources_resource(code)`
  - `resources_resource(company_id)`
  - `production_productionbom(bom_code)`
  - `production_productionbom(service_item_id)`
  - `production_bomline(bom_id)`
  - `production_bomline(resource_id)`
  - `production_bomline(inventory_item_id)`
  - `sales_saleline(assigned_resource_id)`
- Use `db_index=True` in model fields or add indexes in migration

**Test:**

- Run migration on test database
- Use Django debug toolbar to verify indexes are used
- Compare query times before and after indexes

---

### Task 24: Create API Documentation for Resources and BOM

**Status:** Pending  
**Dependencies:** Tasks 11, 12, 13  
**Priority:** Low

**What to do:**

- Create `API_DOCUMENTATION.md` in `zentro-backend/docs/`
- Document all Resources endpoints with curl examples
- Document all Production BOM endpoints
- Document Sales integration endpoints
- Include request/response examples in JSON format
- Add authentication requirements
- Include error response examples
- Add integration guide with step-by-step service sale flow
- Document camelCase field naming conventions

**Test:**

- Follow documentation to make test API calls
- Verify all examples work correctly
- Have another developer review for clarity

---

### Task 25: Write Comprehensive Tests for Resources and BOM

**Status:** Pending  
**Dependencies:** Tasks 10, 12, 13  
**Priority:** Medium

**What to do:**

- Create test files: `resources/tests.py`, `production/tests.py`
- Write model tests: Resource creation, validation, number series
- Write BOM tests: ProductionBOM creation, BOMLine validation, cost calculations, profit margin calculations
- Write API tests: all CRUD endpoints, filtering, search, validation
- Write integration tests: complete service sale flow, BOM processing, inventory deduction
- Write edge case tests: insufficient inventory, inactive resources
- Aim for >80% code coverage

**Test:**

- Run test suite with: `python manage.py test`
- Verify all tests pass
- Check code coverage report
- Add tests for any uncovered critical paths

---

## Summary

**Total Tasks:** 25  
**High Priority:** 10 tasks (must complete first)  
**Medium Priority:** 12 tasks  
**Low Priority:** 3 tasks

**Recommended Order:**

1. Complete Phase 1 (Tasks 1-10) - Backend Foundation
2. Test thoroughly in Django admin
3. Complete Phase 2 (Tasks 11-13) - APIs
4. Complete Phase 3 (Tasks 14-15) - Resources Frontend
5. Complete Phase 4 (Tasks 16-17) - BOM Frontend
6. Complete Phase 5 (Tasks 18-20) - POS Integration
7. Complete Phase 6 (Tasks 21-22) - Reporting (optional)
8. Complete Phase 7 (Tasks 23-25) - Performance & Testing

**Key Files to Reference:**

- PRD: `.taskmaster/docs/resources-production-bom-prd.txt`
- Demo Code: `zentro-backend/demo.txt`
- This Task List: `zentro-backend/RESOURCES_BOM_TASKS.md`


