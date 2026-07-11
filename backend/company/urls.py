from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

app_name = "company"

urlpatterns = [
    path("is-company-existing/", views.is_company_existing, name="is-company-existing"),
    path(
        "check-validity-of-company/",
        views.check_validity_of_company,
        name="check-validity-of-company",
    ),
    path("company-onboarding/", views.company_onboarding, name="company-onboarding"),
    path("task-status/<str:task_id>/", views.get_task_status, name="task-status"),
    path(
        "api/company/task-status/<str:task_id>/",
        views.get_task_status,
        name="task-status",
    ),
    path(
        "api/company/validate-company-name/",
        views.validate_company_name,
        name="validate_company_name",
    ),
    path(
        "api/company/create-company-account/",
        views.create_company_account,
        name="create-company-account",
    ),
    path(
        "api/company/check-company-exists/",
        views.check_company_exists,
        name="check-company-exists",
    ),
    # Company Overview and User Management APIs
    path(
        "api/company/overview/",
        views.company_overview,
        name="company-overview",
    ),
    path(
        "api/company/users/",
        views.company_users,
        name="company-users",
    ),
    path(
        "api/company/users/create/",
        views.create_user,
        name="create-user",
    ),
    path(
        "api/company/users/<int:user_id>/",
        views.update_user,
        name="update-user",
    ),
    path(
        "api/company/users/<int:user_id>/delete/",
        views.delete_user,
        name="delete-user",
    ),
    path(
        "api/company/users/<int:user_id>/toggle-status/",
        views.toggle_user_status,
        name="toggle-user-status",
    ),
    path(
        "api/company/roles/",
        views.get_roles,
        name="get-roles",
    ),
    path(
        "api/company/branches/",
        views.get_branches,
        name="get-branches",
    ),
    path(
        "api/company/branch-limits/",
        views.branch_limits,
        name="branch-limits",
    ),
    path(
        "api/company/branches/add/",
        views.create_branch,
        name="create-branch",
    ),
    path(
        "api/company/upload-logo/",
        views.upload_company_logo,
        name="upload-company-logo",
    ),
    path(
        "api/company/update-info/",
        views.update_company_info,
        name="update-company-info",
    ),
    path(
        "api/company/modules/",
        views.company_modules,
        name="company-modules",
    ),
    path(
        "api/company/modules/toggle/",
        views.toggle_module,
        name="toggle-module",
    ),
    # path(
    #     "/company/check-validity-of-company/",
    #     views.check_validity_of_company,
    #     name="check-validity-of-company",
    # ),
    # Zentro Starter Package URLs (renamed from starter-offer to avoid ad blockers)
    path(
        "api/company/starter-package/",
        views.get_starter_offer,
        name="get-starter-package",
    ),
    path(
        "api/company/starter-order/create/",
        views.create_starter_order,
        name="create-starter-order",
    ),
    path(
        "api/company/starter-payment-intent/",
        views.create_starter_payment_intent,
        name="create-starter-payment-intent",
    ),
    path(
        "api/company/confirm-starter-payment/",
        views.confirm_starter_payment,
        name="confirm-starter-payment",
    ),
    path(
        "api/company/verify-payment-unified/",
        views.verify_payment_unified,
        name="verify-payment-unified",
    ),
    path(
        "api/company/subscription/create-manual-payment/",
        views.create_manual_payment,
        name="create-manual-payment",
    ),
    path(
        "api/company/subscription/create-extra-users-payment/",
        views.create_extra_users_payment,
        name="create-extra-users-payment",
    ),
    path(
        "api/company/subscription/mobile-money-instructions/",
        views.get_mobile_money_instructions,
        name="mobile-money-instructions",
    ),
    path(
        "api/company/starter-orders/",
        views.get_starter_orders,
        name="get-starter-orders",
    ),
    # Installment Payment Management
    path(
        "api/company/starter-register-payment/",
        views.register_manual_payment,
        name="register-manual-payment",
    ),
    path(
        "api/company/starter-payment-receipt/<int:payment_id>/",
        views.get_payment_receipt,
        name="get-payment-receipt",
    ),
    path(
        "api/company/starter-resend-receipt/",
        views.resend_receipt_email,
        name="resend-receipt-email",
    ),
    path(
        "api/company/starter-order-payments/<int:order_id>/",
        views.get_order_payments,
        name="get-order-payments",
    ),
]

router = DefaultRouter()
router.register(
    r"api/company/payment-methods",
    views.PaymentMethodViewSet,
    basename="payment-method",
)
router.register(
    r"api/company/billing-history",
    views.BillingHistoryViewSet,
    basename="billing-history",
)

router.register(
    r"api/company/subscriptions", views.SubscriptionViewSet, basename="subscription"
)
router.register(
    r"api/company/pricing-plans", views.PricingViewSet, basename="pricing-plan"
)

router.register(
    r"api/company/pricing-plans-v2", views.PricingViewSetV2, basename="pricing-plan-v2"
)
router.register(
    r"api/company/add-ons", views.AddOnViewSet, basename="add-on"
)

urlpatterns += router.urls
