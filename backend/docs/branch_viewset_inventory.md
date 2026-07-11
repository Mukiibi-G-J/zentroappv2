# Branch / dimension — ViewSet inventory

This document summarizes how API viewsets relate to **branch (Global Dimension 1)** scoping.  
**Internal field name:** `global_dimension_1` (and related helpers in `dimension/branch_filter.py`).  
**User-facing label:** Branch.

## Central mechanisms

| Mechanism                                                 | Role                                                                                                                                                                                                      |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `filter_queryset_by_branch(qs, user, request=request)`    | Filters querysets when `GeneralLedgerSetup.enable_multiple_branches` is True. Honors `X-Branch-Scope: all` for users with `can_switch_branch`, otherwise uses `X-Branch-Id` or `user.global_dimension_1`. |
| `filter_queryset_by_branch_location(...)`                 | For models tied to `items.Location` via `Location.code == DimensionValue.code` (e.g. restaurant floors/tables).                                                                                           |
| `filter_reservation_queryset(...)`                        | Reservations with optional table; filters by `table.floor.location` when a table is set.                                                                                                                  |
| `FILTER_THROUGH_RELATION` in `dimension/branch_filter.py` | Join path for line/header models (e.g. `restaurantorderitem` → `order`).                                                                                                                                  |

## Legend

- **List filtered:** `get_queryset` applies one of the helpers above (or equivalent).
- **Retrieve safe:** Detail uses filtered queryset (e.g. `get_object` via `filter_queryset(self.get_queryset())`).
- **Model `gdim`:** Model has `global_dimension_1` FK (or filters through a related model that does).

## Sales / purchases (ERP documents)

| ViewSet                 | Model / notes     | List filtered                       | Retrieve safe                                    | Notes                                                                         |
| ----------------------- | ----------------- | ----------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| `SalesViewSet`          | `SalesInvoice`    | Yes                                 | **Yes** (uses filtered queryset in `get_object`) |                                                                               |
| `SalesOrderViewSet`     | `SalesOrder`      | Yes                                 | **Yes**                                          |                                                                               |
| `PurchaseViewSet`       | `PurchaseInvoice` | Yes                                 | **Yes**                                          |                                                                               |
| `CustomerViewSet`       | `Customer`        | No                                  | N/A                                              | Customers are typically company-wide; branch may appear on transactions only. |
| `CustomerLedgerViewSet` | Ledger entries    | Yes (where implemented)             | Verify per action                                |                                                                               |
| `SalesDashboardViewSet` | Aggregations      | Query param `global_dimension_1_id` | N/A                                              | Uses date + optional dimension param; align with frontend branch scope.       |

## Restaurant (`restaurant_management`)

| ViewSet                                       | List filtered | Model / path                                                                                                                 |
| --------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `FloorViewSet`                                | Yes           | `filter_queryset_by_branch_location` → `location`                                                                            |
| `FloorSectionViewSet`                         | Yes           | `floor__location`                                                                                                            |
| `TableViewSet`                                | Yes           | `floor__location`                                                                                                            |
| `ReservationViewSet`                          | Yes           | `filter_reservation_queryset`                                                                                                |
| `RestaurantOrderViewSet`                      | Yes           | `RestaurantOrder.global_dimension_1`; stamped on create via serializer                                                       |
| `RestaurantOrderItemViewSet`                  | Yes           | Through `order` (`FILTER_THROUGH_RELATION`)                                                                                  |
| `RestaurantCheckViewSet`                      | Yes           | Through `order`                                                                                                              |
| `OrderItemModifierViewSet`                    | Yes           | Through `order_item__order`                                                                                                  |
| `OrderActionLogViewSet`                       | Yes           | Through `order`                                                                                                              |
| `RestaurantDashboardViewSet.stats`            | Yes           | Uses filtered order/reservation querysets                                                                                    |
| Menu builder viewsets (`Menu`, `MenuItem`, …) | No / partial  | Menus are often shared; location linkage is via `MenuLocation` — review per endpoint if strict branch isolation is required. |

## Other apps (representative)

| Area                                              | Branch helper usage                                                                                           | Notes                                                                        |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `expenses`, `loans`, `prepayment`, `bank_account` | `filter_queryset_by_branch` where wired                                                                       | Confirm each `get_object` uses filtered queryset.                            |
| `items` (ledgers, journals)                       | Mixed: ledgers use dimension; shared `Item` catalog is not filtered by branch in `filter_queryset_by_branch`. | Stock is branch-aware via ledger lines.                                      |
| `payments.PaymentJournalViewSet`                  | Not wired                                                                                                     | `PaymentJournal` may lack `global_dimension_1` — product decision.           |
| `hotel_management`                                | Not wired                                                                                                     | Add branch model/FK or location linkage if multi-branch hotels are required. |
| `postings` (posting groups)                       | Not wired                                                                                                     | Usually global configuration.                                                |
| `reports.ReportsViewSet`                          | `get_branch_for_request` + query `branch=all`                                                                 | Report-specific branch override.                                             |

## Maintenance

When adding a new `ModelViewSet`:

1. Prefer **stamping** `global_dimension_1` on create from `get_branch_for_request(request)` (or inherited from header document).
2. Call **`filter_queryset_by_branch`** in `get_queryset` (or add a `FILTER_THROUGH_RELATION` entry if filtering through a FK).
3. Override **`get_object`** only if you need non-PK lookup; otherwise ensure it uses **`filter_queryset(self.get_queryset())`** so detail routes cannot cross branches.
