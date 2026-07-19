from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import restaurant_auth
from .views import (
    VerifyOTPView,
    ForgotPasswordView,
    VerifyForgotPasswordOTPView,
    ResetPasswordView,
    RoleViewSet,
    PermissionView,
    UserSetupViewSet,
)
from .user_management_views import (
    UserManagementViewSet,
    UserGroupViewSet,
    RoleViewSet as RoleManagementViewSet,
    RoleCenterViewSet,
    ObjectsViewSet,
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r"api/authentication/roles", RoleViewSet, basename="role")

# User Management API routes
router.register(r"api/users", UserManagementViewSet, basename="user-management")
router.register(r"api/user-groups", UserGroupViewSet, basename="user-group")
router.register(
    r"api/management/roles", RoleManagementViewSet, basename="role-management"
)
router.register(r"api/role-centers", RoleCenterViewSet, basename="role-center")
router.register(r"api/objects", ObjectsViewSet, basename="objects")
router.register(r"api/user-setup", UserSetupViewSet, basename="user-setup")

app_name = "authentication"

urlpatterns = [
    path("api/auth/resend-otp/", views.ResendOTPView.as_view(), name="resend-otp"),
]


# web endpoionts
urlpatterns += [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify-company/", views.verify_company_view, name="verify-company"),
    path(
        "verify-account/<str:email>/", views.verify_account_view, name="verify-account"
    ),
]

# ----- API VUEW ------
urlpatterns += [
    path(
        "api/auth/is-company-exists/",
        views.IsCompanyExisting.as_view(),
        name="is-company-exists",
    ),
    path(
        "api/auth/restaurant-app/company-lookup/",
        restaurant_auth.RestaurantAppCompanyLookupView.as_view(),
        name="restaurant-app-company-lookup",
    ),
    path(
        "api/auth/login-pin/",
        restaurant_auth.RestaurantPinLoginView.as_view(),
        name="restaurant-login-pin",
    ),
    path(
        "api/auth/pin/",
        restaurant_auth.RestaurantStaffPinLoginView.as_view(),
        name="restaurant-staff-pin-login",
    ),
    path(
        "api/auth/pin/device-context/",
        restaurant_auth.RestaurantPinDeviceContextView.as_view(),
        name="restaurant-pin-device-context",
    ),
    path(
        "api/auth/restaurant-staff/enroll/",
        restaurant_auth.RestaurantStaffEnrollView.as_view(),
        name="restaurant-staff-enroll",
    ),
    path(
        "api/auth/restaurant-pin/status/",
        restaurant_auth.RestaurantPinStatusView.as_view(),
        name="restaurant-pin-status",
    ),
    path("api/auth/token/", views.AuthTokenView.as_view(), name="token_obtain_pair"),
    path("api/auth/me/", views.AuthMeView.as_view(), name="auth-me"),
    path(
        "api/auth/exit-impersonation/",
        views.ExitImpersonationView.as_view(),
        name="exit-impersonation",
    ),
    path("api/auth/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path(
        "api/auth/forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password",
    ),
    path(
        "api/auth/verify-forgot-password-otp/",
        VerifyForgotPasswordOTPView.as_view(),
        name="verify-forgot-password-otp",
    ),
    path(
        "api/auth/reset-password/", ResetPasswordView.as_view(), name="reset-password"
    ),
    path("api/auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("api/auth/profile/", views.get_user_profile, name="get-user-profile"),
    path(
        "api/auth/update-profile/",
        views.update_user_profile,
        name="update-user-profile",
    ),
    path("api/auth/upload-avatar/", views.upload_avatar, name="upload-avatar"),
    path("api/auth/remove-avatar/", views.remove_avatar, name="remove-avatar"),
    path("api/auth/change-password/", views.change_password, name="change-password"),
    path(
        "api/auth/device-push-token/",
        views.register_device_push_token,
        name="register-device-push-token",
    ),
    path(
        "api/authentication/permissions/", PermissionView.as_view(), name="permissions"
    ),
]

# Include router URLs
urlpatterns += router.urls
