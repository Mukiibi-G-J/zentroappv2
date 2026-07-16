from django.shortcuts import render, redirect, HttpResponse
from authentication.decorators import tenant_required
from django.contrib.auth import authenticate, logout, login as auth_login
from django.contrib import messages
from django.db import connection as db_connection
from django_tenants.utils import get_tenant, schema_context
from django.conf import settings

from rest_framework.views import APIView
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from authentication.models import OTP, PasswordResetToken, CustomUser as User, Role
from authentication.forms import LoginForm, VerifyCompanyForm
from authentication.serializers import ResendOTPSerializer, AuthTokenViewSerializer
from authentication.session_context import build_auth_session_payload
from authentication.login_utils import find_user_by_phone
from helpers.helpers import (
    send_verification_otp,
    send_forgot_password_link_email,
    send_plain_sms,
)


def _otp_channel_from_delivery(result: dict) -> str:
    if result.get("email") and result.get("sms"):
        return "both"
    if result.get("sms"):
        return "sms"
    return "email"


def _verification_delivery_message(result: dict) -> str:
    if result.get("email") and result.get("sms"):
        return "Verification code sent to your email and phone."
    if result.get("sms"):
        return "Verification code sent to your phone."
    return "Verification code sent to your email."
from helpers.send_email import send_transactional_email
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from company.models import Company

from django.shortcuts import render
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
    parser_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
import logging
from django.utils.timezone import now

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_user_profile(request):
    """
    Get current user's profile information
    """
    try:
        user = request.user
        user_roles = [role.name for role in user.roles.all()]

        profile_data = {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "roles": user_roles,
            "authority": user.get_authority(),
            "global_dimension_1": (
                {
                    "id": user.global_dimension_1.id,
                    "code": user.global_dimension_1.code,
                    "description": user.global_dimension_1.description or "",
                }
                if user.global_dimension_1
                else None
            ),
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "avatar_url": (
                request.build_absolute_uri(user.avatar.url) if user.avatar else None
            ),
        }

        return Response(profile_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return Response(
            {"error": "Failed to fetch profile"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class AuthMeView(APIView):
    """GET /api/auth/me/ — current user, application profile, Role Centre page, nav items."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        auth = getattr(request, 'auth', None)
        schema_name = None
        if auth is not None:
            try:
                schema_name = auth.get('schema_name')
            except (AttributeError, TypeError):
                schema_name = None

        if not schema_name:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from company.models import Company
            from django.db import connection as db_connection

            tenant = Company.objects.get(schema_name=schema_name)
            with schema_context(schema_name):
                db_connection.set_tenant(tenant)
                payload = build_auth_session_payload(request.user, request)
            return Response(payload, status=status.HTTP_200_OK)
        except Company.DoesNotExist:
            return Response({'error': 'Unknown tenant'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error('Error building auth session: %s', e)
            return Response(
                {'error': 'Failed to load session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def register_device_push_token(request):
    """Register or refresh the current user's FCM device token."""
    from authentication.models import DevicePushToken

    fcm_token = (request.data.get("fcm_token") or "").strip()
    device_id = (request.data.get("device_id") or "").strip()
    platform = (request.data.get("platform") or "android").strip().lower()[:16]

    if not fcm_token or not device_id:
        return Response(
            {"error": "fcm_token and device_id are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    DevicePushToken.objects.update_or_create(
        user=request.user,
        device_id=device_id,
        defaults={
            "fcm_token": fcm_token,
            "platform": platform or "android",
            "is_active": True,
        },
    )

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def update_user_profile(request):
    """
    Update current user's profile information
    """
    try:
        user = request.user

        # Update allowed fields
        if "full_name" in request.data:
            user.full_name = request.data["full_name"]

        if "email" in request.data:
            # Check if email is already taken by another user
            if (
                get_user_model()
                .objects.filter(email=request.data["email"])
                .exclude(id=user.id)
                .exists()
            ):
                return Response(
                    {"error": "Email is already taken"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.email = request.data["email"]

        if "phone_number" in request.data:
            # Check if phone is already taken by another user
            if (
                get_user_model()
                .objects.filter(phone_number=request.data["phone_number"])
                .exclude(id=user.id)
                .exists()
            ):
                return Response(
                    {"error": "Phone number is already taken"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.phone_number = request.data["phone_number"]

        user.save()

        # Return updated profile
        user_roles = [role.name for role in user.roles.all()]
        profile_data = {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "roles": user_roles,
            "authority": user.get_authority(),
            "global_dimension_1": (
                {
                    "id": user.global_dimension_1.id,
                    "code": user.global_dimension_1.code,
                    "description": user.global_dimension_1.description or "",
                }
                if user.global_dimension_1
                else None
            ),
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "avatar_url": (
                request.build_absolute_uri(user.avatar.url) if user.avatar else None
            ),
        }

        return Response(profile_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        return Response(
            {"error": "Failed to update profile"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@parser_classes([MultiPartParser, FormParser])
def upload_avatar(request):
    """
    Upload user avatar/profile picture
    """
    try:
        user = request.user

        if "avatar" not in request.FILES:
            return Response(
                {"error": "No avatar file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avatar_file = request.FILES["avatar"]

        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if avatar_file.content_type not in allowed_types:
            return Response(
                {"error": "Invalid file type. Please upload a JPEG, PNG, or GIF image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (max 5MB)
        if avatar_file.size > 5 * 1024 * 1024:
            return Response(
                {
                    "error": "File size too large. Please upload an image smaller than 5MB"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save the avatar
        user.avatar = avatar_file
        user.save()

        # Return updated profile data
        user_roles = [role.name for role in user.roles.all()]
        profile_data = {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "roles": user_roles,
            "authority": user.get_authority(),
            "global_dimension_1": (
                {
                    "id": user.global_dimension_1.id,
                    "code": user.global_dimension_1.code,
                    "description": user.global_dimension_1.description or "",
                }
                if user.global_dimension_1
                else None
            ),
            "is_staff": user.is_staff,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "avatar_url": (
                request.build_absolute_uri(user.avatar.url) if user.avatar else None
            ),
        }

        return Response(profile_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error uploading avatar: {str(e)}")
        return Response(
            {"error": "Failed to upload avatar"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def remove_avatar(request):
    user = request.user
    user.avatar = None
    user.save()
    return Response({"success": True, "avatar_url": None})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def change_password(request):
    """
    Change user's password
    """
    try:
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Validate current password
        if not user.check_password(current_password):
            return Response(
                {"error": "Current password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate new password
        if new_password != confirm_password:
            return Response(
                {"error": "New passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new password
        user.set_password(new_password)
        if getattr(user, "must_change_password", False):
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password"])
        else:
            user.save(update_fields=["password"])

        refresh = AuthTokenViewSerializer.get_token(user)
        return Response(
            {
                "message": "Password changed successfully",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        return Response(
            {"error": "Failed to change password"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# -------------------------- api start points -------------------------------
class ResendOTPView(APIView):
    """
    Unauthenticated-friendly: users who just logged in are often still
    is_verified=False, and CustomJWTAuthentication rejects those tokens with 401.
    """

    serializer_class = ResendOTPSerializer
    queryset = OTP.objects.none()
    permission_classes = [AllowAny]
    # Required: default CustomJWTAuthentication rejects is_verified=False tokens.
    authentication_classes = []

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = (serializer.validated_data.get("email") or "").strip()
        phone = (serializer.validated_data.get("phone") or "").strip()
        channel = serializer.validated_data.get("channel", "email")

        try:
            tenant = get_tenant(request)
        except Exception:
            tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {
                    "message": "Could not resolve your company. "
                    "Use your company link or subdomain, then resend the code."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context(tenant.schema_name):
            user = None
            if channel == "sms" and phone:
                user = find_user_by_phone(phone)
                if not user:
                    return Response(
                        {"phone": ["User does not exist"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif email:
                try:
                    user = User.objects.get(email__iexact=email)
                except User.DoesNotExist:
                    return Response(
                        {"email": ["User does not exist"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"message": "Email or phone is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        delivery = send_verification_otp(user, tenant.schema_name)
        if delivery["success"]:
            return Response(
                {
                    "message": _verification_delivery_message(delivery),
                    "otp_channel": _otp_channel_from_delivery(delivery),
                }
            )
        return Response(
            {
                "message": "Could not send verification code. "
                "Check mail/SMS configuration or try again later."
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )


class SendContactEmailView(APIView):
    """Public endpoint to send contact form data via email from landing page."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            name = request.data.get("name", "")
            email = request.data.get("email", "")
            phone = request.data.get("phone", "")
            message = request.data.get("message", "")

            if not email or not message.strip():
                return Response(
                    {"message": "Email and message are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            to_email = "zentroapp.app@gmail.com"
            subject = "Contact Form - ZentroApp Landing Page"

            html = f"""
            <h2>New Contact Form Submission</h2>
            <p><strong>Name:</strong> {name or "(not provided)"}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Phone:</strong> {phone or "(not provided)"}</p>
            <p><strong>Message:</strong></p>
            <p>{message}</p>
            """
            plain = f"Name: {name or '(not provided)'}\nEmail: {email}\nPhone: {phone or '(not provided)'}\n\nMessage:\n{message}"

            success = send_transactional_email(
                to=to_email,
                subject=subject,
                html=html,
                plain_message=plain,
            )
            if not success:
                return Response(
                    {"message": "Failed to send email"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response({"message": "Email sent"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyOTPView(APIView):
    """
    Must work for is_verified=False users; JWT auth rejects them with 401 otherwise.
    Tenant is resolved from the request host (company subdomain).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            email = (request.data.get("email") or "").strip()
            otp = request.data.get("otp")

            if not email or not otp:
                return Response(
                    {"message": "Email and OTP are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                tenant = get_tenant(request)
            except Exception:
                tenant = getattr(request, "tenant", None)
            if not tenant:
                return Response(
                    {
                        "message": "Could not resolve your company. "
                        "Use your company subdomain to verify your email."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with schema_context(tenant.schema_name):
                user = User.objects.get(email__iexact=email)
                otpvalid = OTP.objects.get(user=user)

                if otpvalid.validate_otp(otp):
                    user.is_verified = True
                    user.save()
                    # schema_context alone leaves connection.tenant as FakeTenant;
                    # get_token needs the real Company for subscription/JWT claims.
                    db_connection.set_tenant(tenant)
                    refresh = AuthTokenViewSerializer.get_token(user)
                    return Response(
                        {
                            "message": "Email verified successfully",
                            "access": str(refresh.access_token),
                            "refresh": str(refresh),
                        },
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {"message": "Invalid OTP"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OTP.DoesNotExist:
            return Response(
                {"message": "No OTP found for this user"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuthTokenView(TokenObtainPairView):
    serializer_class = AuthTokenViewSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.context["request"] = request
        serializer.is_valid(raise_exception=True)

        user = serializer.user
        # ✅ manually update last_login
        user.last_login = now()
        user.save(update_fields=["last_login"])

        response_data = dict(serializer.validated_data)

        if not user.is_verified:
            tenant = get_tenant(request)
            schema_name = getattr(tenant, "schema_name", None)
            delivery = send_verification_otp(user, schema_name)
            response_data["otp_channel"] = _otp_channel_from_delivery(delivery)
            if not delivery["success"]:
                logger.warning(
                    "Verification OTP delivery failed after login for %s (tenant %s)",
                    user.email,
                    schema_name,
                )
            elif not delivery.get("email") or (
                user.phone_number and not delivery.get("sms")
            ):
                logger.warning(
                    "Partial verification OTP delivery for %s (tenant %s): %s",
                    user.email,
                    schema_name,
                    delivery,
                )

        # Attach Role Centre session so the SPA has nav even before /api/auth/me/
        try:
            session = build_auth_session_payload(user, request)
            response_data.update(session)
        except Exception as e:
            logger.warning("Login session payload failed: %s", e)

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # For now, just return success since we're not using blacklisting
            # The custom authentication will handle token validation
            return Response(
                {"message": "Successfully logged out"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"message": "Error during logout"}, status=status.HTTP_400_BAD_REQUEST
            )


class IsCompanyExisting(APIView):
    def post(self, request):
        company_name = request.data.get("company_name")
        if Company.objects.filter(name=company_name).exists():
            return Response({"message": "Company exists"}, status=status.HTTP_200_OK)
        return Response(
            {"message": "Company does not exist"}, status=status.HTTP_404_NOT_FOUND
        )


# -------------------------- end of api end points -------------------------------


@tenant_required
def login_view(request):
    if request.user.is_authenticated:
        return redirect("sales:sales-dashboard")
    if request.method == "POST":
        print("POST data:", request.POST)
        form = LoginForm(data=request.POST)
        user = User.objects.filter(email=request.POST.get("email")).first()
        if not user:
            messages.warning(
                request, f"User with email {request.POST.get('email')} does not exist"
            )
            return render(
                request,
                "authentication/login.html",
                {"form": form, "email": request.POST.get("email")},
            )
        print("form", form.is_valid())
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            print("user alll", User.objects.all())
            user = authenticate(request, username=email, password=password)
            if user is None:
                form.add_error("password", "Invalid password")
                messages.warning(request, "Invalid password")

                return render(
                    request,
                    "authentication/login.html",
                    # persist the form data
                    {"form": form, "email": email, "password": password},
                )
            if user.is_verified == False:
                return redirect("authentication:verify-account", user.email)
            if user:
                auth_login(request, user)
                return redirect("sales:sales-dashboard")
    else:
        form = LoginForm()

    return render(request, "authentication/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("authentication:login")


def verify_company_view(request):
    form = VerifyCompanyForm()
    if request.method == "POST":
        form = VerifyCompanyForm(request.POST)
        if form.is_valid():
            company_name = form.cleaned_data["company_name"]
            if Company.objects.filter(name=company_name).exists():
                # get domain and redirect user to login page company.domain_url
                company = Company.objects.get(name=company_name)
                protocol = "https" if request.is_secure() else "http"
                # get port number

                if settings.ENVIRONMENT == "development":
                    url = f"{protocol}://{company.domain_url}:8000/login"
                    print(url)
                else:
                    url = f"{protocol}://{company.domain_url}/login"
                    print(url)
                return redirect(url)
            else:
                form.add_error("company_name", "Company name is invalid")
    return render(request, "authentication/verify-company.html", {"form": form})


def verify_account_view(request, email):
    with schema_context(request.tenant.schema_name):
        user = User.objects.get(email=email)
        if request.method == "GET":
            delivery = send_verification_otp(user, request.tenant.schema_name)
            if delivery["success"]:
                messages.info(
                    request, _verification_delivery_message(delivery)
                )
            else:
                messages.error(
                    request,
                    "Could not send verification code. Please try again later.",
                )
            return render(
                request, "authentication/verify-account.html", {"email": email}
            )

        if request.method == "POST":
            otp = request.POST.get("otp")
            if otp:
                otpvalid = OTP.objects.get(user=user)
                if otpvalid.validate_otp(otp):
                    user.is_verified = True
                    user.save()
                    messages.success(request, "Account verified successfully!")
                    return redirect("authentication:login")
                else:
                    messages.error(
                        request, "Invalid verification code. Please try again."
                    )
                    return redirect("authentication:verify-account", email)

        return render(request, "authentication/verify-account.html", {"email": email})


# -------------------------- Forgot Password Endpoints -------------------------------


class ForgotPasswordView(APIView):
    """
    Send password reset link to user's email (link-based, industry standard).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        import hashlib
        import secrets

        try:
            email = request.data.get("email")

            if not email:
                return Response(
                    {"error": "Email is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tenant = get_tenant(request)

            with schema_context(tenant.schema_name):
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    return Response(
                        {"error": "No user found with this email address"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Invalidate any existing tokens for this user
                PasswordResetToken.objects.filter(user=user).delete()

                # Create secure token
                token = secrets.token_urlsafe(48)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                from django.utils import timezone
                from datetime import timedelta

                PasswordResetToken.objects.create(
                    user=user,
                    token_hash=token_hash,
                    expires_at=timezone.now() + timedelta(hours=1),
                )

                # Build reset URL - use Origin/Referer for tenant subdomain
                origin = (
                    request.META.get("HTTP_ORIGIN")
                    or request.META.get("HTTP_REFERER", "").rsplit("/", 1)[0]
                )
                if not origin:
                    origin = f"https://{tenant.schema_name}.{getattr(settings, 'DOMAIN', 'zentroapp.app')}"
                reset_url = f"{origin.rstrip('/')}/reset-password?token={token}"

                sent = send_forgot_password_link_email(
                    user.email, user, tenant.schema_name, reset_url
                )

                if not sent:
                    return Response(
                        {
                            "error": "Failed to send reset email. Please try again later.",
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

                return Response(
                    {
                        "message": "If an account exists with this email, you will receive a password reset link shortly.",
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error(f"Error in forgot password: {str(e)}")
            return Response(
                {"error": "Failed to send reset email. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyForgotPasswordOTPView(APIView):
    """
    Verify OTP for password reset
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            email = request.data.get("email")
            otp = request.data.get("otp")

            if not email or not otp:
                return Response(
                    {"error": "Email and OTP are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tenant = get_tenant(request)

            with schema_context(tenant.schema_name):
                try:
                    user = User.objects.get(email=email)
                    otp_obj = OTP.objects.get(user=user)
                except User.DoesNotExist:
                    return Response(
                        {"error": "User not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                except OTP.DoesNotExist:
                    return Response(
                        {"error": "No OTP found for this user"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if otp_obj.validate_otp(otp):
                    # Generate a temporary reset token (you can use JWT or a simple token)
                    from rest_framework_simplejwt.tokens import RefreshToken

                    refresh = RefreshToken.for_user(user)
                    reset_token = str(refresh.access_token)

                    return Response(
                        {
                            "message": "OTP verified successfully",
                            "reset_token": reset_token,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"error": "Invalid or expired OTP"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        except Exception as e:
            logger.error(f"Error verifying forgot password OTP: {str(e)}")
            return Response(
                {"error": "Failed to verify OTP. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetPasswordView(APIView):
    """
    Reset password using token from reset link (link-based flow).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        import hashlib

        try:
            reset_token = request.data.get("reset_token") or request.data.get("token")
            new_password = request.data.get("new_password")

            if not reset_token or not new_password:
                return Response(
                    {"error": "Reset token and new password are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if len(new_password) < 8:
                return Response(
                    {"error": "Password must be at least 8 characters long"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tenant = get_tenant(request)
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

            with schema_context(tenant.schema_name):
                try:
                    prt = PasswordResetToken.objects.get(token_hash=token_hash)
                except PasswordResetToken.DoesNotExist:
                    return Response(
                        {"error": "Invalid or expired reset link. Please request a new one."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not prt.is_valid(reset_token):
                    prt.delete()
                    return Response(
                        {"error": "Reset link has expired. Please request a new one."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user = prt.user
                user.set_password(new_password)
                user.save()
                prt.delete()

                return Response(
                    {"message": "Password reset successfully"},
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error(f"Error resetting password: {str(e)}")
            return Response(
                {"error": "Failed to reset password. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------- Role Management Endpoints -------------------------------


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles
    """

    queryset = Role.objects.all()
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter roles based on query parameters"""
        queryset = Role.objects.all()

        # Filter by active status if specified
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")

    def list(self, request, *args, **kwargs):
        """List all roles with user count"""
        queryset = self.get_queryset()

        # Add user count to each role
        roles_data = []
        for role in queryset:
            role_data = {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions,
                "isActive": role.is_active,
                "createdAt": role.created_at.isoformat(),
                "updatedAt": role.updated_at.isoformat(),
                "userCount": role.users.count(),
            }
            roles_data.append(role_data)

        return Response(roles_data)

    def create(self, request, *args, **kwargs):
        """Create a new role"""
        try:
            name = request.data.get("name")
            description = request.data.get("description")
            permissions = request.data.get("permissions", [])
            is_active = request.data.get("isActive", True)

            # Validate required fields - only name is required for initial creation
            if not name:
                return Response(
                    {"error": "Role name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Set default description if not provided
            if not description:
                description = f"Role: {name}"

            # Check if role name already exists
            if Role.objects.filter(name__iexact=name).exists():
                return Response(
                    {"error": "A role with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create the role
            role = Role.objects.create(
                name=name,
                description=description,
                permissions=permissions,
                is_active=is_active,
            )

            role_data = {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions,
                "isActive": role.is_active,
                "createdAt": role.created_at.isoformat(),
                "updatedAt": role.updated_at.isoformat(),
                "userCount": 0,
            }

            return Response(role_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating role: {str(e)}")
            return Response(
                {"error": "Failed to create role"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        """Update an existing role"""
        try:
            role = self.get_object()

            # Update fields if provided
            if "name" in request.data:
                name = request.data["name"]
                # Check if name is already taken by another role
                if Role.objects.filter(name__iexact=name).exclude(id=role.id).exists():
                    return Response(
                        {"error": "A role with this name already exists"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                role.name = name

            if "description" in request.data:
                role.description = request.data["description"]

            if "permissions" in request.data:
                role.permissions = request.data["permissions"]

            if "isActive" in request.data:
                role.is_active = request.data["isActive"]

            role.save()

            role_data = {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions,
                "isActive": role.is_active,
                "createdAt": role.created_at.isoformat(),
                "updatedAt": role.updated_at.isoformat(),
                "userCount": role.users.count(),
            }

            return Response(role_data)

        except Exception as e:
            logger.error(f"Error updating role: {str(e)}")
            return Response(
                {"error": "Failed to update role"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a role"""
        try:
            role = self.get_object()

            # Check if role has users assigned
            if role.users.exists():
                return Response(
                    {
                        "error": "Cannot delete role with assigned users. Please reassign users first."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            role.delete()
            return Response({"message": "Role deleted successfully"})

        except Exception as e:
            logger.error(f"Error deleting role: {str(e)}")
            return Response(
                {"error": "Failed to delete role"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        """Get users assigned to this role"""
        role = self.get_object()
        users = role.users.all()

        users_data = []
        for user in users:
            user_data = {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "fullName": user.full_name,
                "phoneNumber": user.phone_number,
                "isActive": user.is_active,
                "isVerified": user.is_verified,
            }
            users_data.append(user_data)

        return Response(users_data)

    @action(detail=True, methods=["post"])
    def assign_users(self, request, pk=None):
        """Assign users to this role"""
        role = self.get_object()
        user_ids = request.data.get("userIds", [])

        try:
            users = User.objects.filter(id__in=user_ids)
            role.users.add(*users)
            return Response(
                {"message": f"Successfully assigned {len(users)} users to role"}
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def remove_users(self, request, pk=None):
        """Remove users from this role"""
        role = self.get_object()
        user_ids = request.data.get("userIds", [])

        try:
            users = User.objects.filter(id__in=user_ids)
            role.users.remove(*users)
            return Response(
                {"message": f"Successfully removed {len(users)} users from role"}
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PermissionView(APIView):
    """
    View for getting available permissions
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def get(self, request):
        """Get comprehensive list of all available permissions"""
        permissions_data = [
            # ==================== CORE SYSTEM PERMISSIONS ====================
            {
                "key": "view_dashboard",
                "label": "View Dashboard",
                "category": "Core System",
                "description": "Access to main dashboard and overview",
            },
            {
                "key": "view_profile",
                "label": "View Profile",
                "category": "Core System",
                "description": "View own user profile",
            },
            {
                "key": "edit_profile",
                "label": "Edit Profile",
                "category": "Core System",
                "description": "Edit own user profile",
            },
            # ==================== SALES MODULE PERMISSIONS ====================
            {
                "key": "view_sales",
                "label": "View Sales",
                "category": "Sales",
                "description": "View sales transactions and reports",
            },
            {
                "key": "create_sales",
                "label": "Create Sales",
                "category": "Sales",
                "description": "Create new sales transactions",
            },
            {
                "key": "edit_sales",
                "label": "Edit Sales",
                "category": "Sales",
                "description": "Edit existing sales transactions",
            },
            {
                "key": "delete_sales",
                "label": "Delete Sales",
                "category": "Sales",
                "description": "Delete sales transactions",
            },
            {
                "key": "view_sales_history",
                "label": "View Sales History",
                "category": "Sales",
                "description": "View sales transaction history",
            },
            {
                "key": "create_sales_invoice",
                "label": "Create Sales Invoice",
                "category": "Sales",
                "description": "Create sales invoices",
            },
            # ==================== PURCHASES MODULE PERMISSIONS ====================
            {
                "key": "view_purchases",
                "label": "View Purchases",
                "category": "Purchases",
                "description": "View purchase transactions and reports",
            },
            {
                "key": "create_purchases",
                "label": "Create Purchases",
                "category": "Purchases",
                "description": "Create new purchase transactions",
            },
            {
                "key": "edit_purchases",
                "label": "Edit Purchases",
                "category": "Purchases",
                "description": "Edit existing purchase transactions",
            },
            {
                "key": "delete_purchases",
                "label": "Delete Purchases",
                "category": "Purchases",
                "description": "Delete purchase transactions",
            },
            {
                "key": "view_purchase_history",
                "label": "View Purchase History",
                "category": "Purchases",
                "description": "View purchase transaction history",
            },
            # ==================== ITEMS MODULE PERMISSIONS ====================
            {
                "key": "view_items",
                "label": "View Items",
                "category": "Items",
                "description": "View inventory items and product catalog",
            },
            {
                "key": "create_items",
                "label": "Create Items",
                "category": "Items",
                "description": "Add new inventory items",
            },
            {
                "key": "edit_items",
                "label": "Edit Items",
                "category": "Items",
                "description": "Edit inventory items",
            },
            {
                "key": "delete_items",
                "label": "Delete Items",
                "category": "Items",
                "description": "Delete inventory items",
            },
            {
                "key": "manage_item_categories",
                "label": "Manage Item Categories",
                "category": "Items",
                "description": "Create and manage item categories",
            },
            {
                "key": "manage_item_units",
                "label": "Manage Item Units",
                "category": "Items",
                "description": "Manage units of measure for items",
            },
            # ==================== INVENTORY MODULE PERMISSIONS ====================
            {
                "key": "view_inventory",
                "label": "View Inventory",
                "category": "Inventory",
                "description": "View inventory levels and stock reports",
            },
            {
                "key": "adjust_inventory",
                "label": "Adjust Inventory",
                "category": "Inventory",
                "description": "Make inventory adjustments and stock corrections",
            },
            {
                "key": "view_inventory_history",
                "label": "View Inventory History",
                "category": "Inventory",
                "description": "View inventory movement history",
            },
            {
                "key": "manage_inventory_tracking",
                "label": "Manage Inventory Tracking",
                "category": "Inventory",
                "description": "Manage inventory tracking codes",
            },
            # ==================== CUSTOMERS MODULE PERMISSIONS ====================
            {
                "key": "view_customers",
                "label": "View Customers",
                "category": "Customers",
                "description": "View customer information",
            },
            {
                "key": "create_customers",
                "label": "Create Customers",
                "category": "Customers",
                "description": "Create new customers",
            },
            {
                "key": "edit_customers",
                "label": "Edit Customers",
                "category": "Customers",
                "description": "Edit customer information",
            },
            {
                "key": "delete_customers",
                "label": "Delete Customers",
                "category": "Customers",
                "description": "Delete customers",
            },
            # ==================== VENDORS MODULE PERMISSIONS ====================
            {
                "key": "view_vendors",
                "label": "View Vendors",
                "category": "Vendors",
                "description": "View vendor information",
            },
            {
                "key": "create_vendors",
                "label": "Create Vendors",
                "category": "Vendors",
                "description": "Create new vendors",
            },
            {
                "key": "edit_vendors",
                "label": "Edit Vendors",
                "category": "Vendors",
                "description": "Edit vendor information",
            },
            {
                "key": "delete_vendors",
                "label": "Delete Vendors",
                "category": "Vendors",
                "description": "Delete vendors",
            },
            # ==================== EXPENSES MODULE PERMISSIONS ====================
            {
                "key": "view_expenses",
                "label": "View Expenses",
                "category": "Expenses",
                "description": "View expense transactions and reports",
            },
            {
                "key": "create_expenses",
                "label": "Create Expenses",
                "category": "Expenses",
                "description": "Create new expense transactions",
            },
            {
                "key": "edit_expenses",
                "label": "Edit Expenses",
                "category": "Expenses",
                "description": "Edit existing expense transactions",
            },
            {
                "key": "delete_expenses",
                "label": "Delete Expenses",
                "category": "Expenses",
                "description": "Delete expense transactions",
            },
            {
                "key": "view_expense_history",
                "label": "View Expense History",
                "category": "Expenses",
                "description": "View expense transaction history",
            },
            # ==================== PAYMENTS MODULE PERMISSIONS ====================
            {
                "key": "view_payments",
                "label": "View Payments",
                "category": "Payments",
                "description": "View payment transactions and reports",
            },
            {
                "key": "create_payments",
                "label": "Create Payments",
                "category": "Payments",
                "description": "Create new payment transactions",
            },
            {
                "key": "edit_payments",
                "label": "Edit Payments",
                "category": "Payments",
                "description": "Edit existing payment transactions",
            },
            {
                "key": "delete_payments",
                "label": "Delete Payments",
                "category": "Payments",
                "description": "Delete payment transactions",
            },
            {
                "key": "view_payment_history",
                "label": "View Payment History",
                "category": "Payments",
                "description": "View payment transaction history",
            },
            {
                "key": "manage_payment_methods",
                "label": "Manage Payment Methods",
                "category": "Payments",
                "description": "Configure payment methods",
            },
            # ==================== FINANCIALS MODULE PERMISSIONS ====================
            {
                "key": "view_financials",
                "label": "View Financials",
                "category": "Financials",
                "description": "View financial reports and data",
            },
            {
                "key": "create_financials",
                "label": "Create Financials",
                "category": "Financials",
                "description": "Create financial transactions",
            },
            {
                "key": "edit_financials",
                "label": "Edit Financials",
                "category": "Financials",
                "description": "Edit financial transactions",
            },
            {
                "key": "delete_financials",
                "label": "Delete Financials",
                "category": "Financials",
                "description": "Delete financial transactions",
            },
            {
                "key": "view_chart_of_accounts",
                "label": "View Chart of Accounts",
                "category": "Financials",
                "description": "View chart of accounts",
            },
            {
                "key": "manage_chart_of_accounts",
                "label": "Manage Chart of Accounts",
                "category": "Financials",
                "description": "Create and manage chart of accounts",
            },
            {
                "key": "view_profit_loss",
                "label": "View Profit & Loss",
                "category": "Financials",
                "description": "View profit and loss statements",
            },
            {
                "key": "view_balance_sheet",
                "label": "View Balance Sheet",
                "category": "Financials",
                "description": "View balance sheet reports",
            },
            # ==================== REPORTS MODULE PERMISSIONS ====================
            {
                "key": "view_reports",
                "label": "View Reports",
                "category": "Reports",
                "description": "View all system reports",
            },
            {
                "key": "export_reports",
                "label": "Export Reports",
                "category": "Reports",
                "description": "Export reports to various formats",
            },
            {
                "key": "create_custom_reports",
                "label": "Create Custom Reports",
                "category": "Reports",
                "description": "Create custom report configurations",
            },
            # ==================== USER MANAGEMENT PERMISSIONS ====================
            {
                "key": "manage_users",
                "label": "Manage Users",
                "category": "User Management",
                "description": "Create, edit, and manage users",
            },
            {
                "key": "manage_roles",
                "label": "Manage Roles",
                "category": "User Management",
                "description": "Create, edit, and manage roles",
            },
            {
                "key": "view_user_activity",
                "label": "View User Activity",
                "category": "User Management",
                "description": "View user activity logs",
            },
            # ==================== COMPANY MANAGEMENT PERMISSIONS ====================
            {
                "key": "view_company",
                "label": "View Company",
                "category": "Company Management",
                "description": "View company information",
            },
            {
                "key": "edit_company",
                "label": "Edit Company",
                "category": "Company Management",
                "description": "Edit company information",
            },
            {
                "key": "manage_company_settings",
                "label": "Manage Company Settings",
                "category": "Company Management",
                "description": "Manage company-wide settings",
            },
            # ==================== CONFIGURATION PERMISSIONS ====================
            {
                "key": "view_config_packages",
                "label": "View Config Packages",
                "category": "Configuration",
                "description": "View configuration packages",
            },
            {
                "key": "manage_config_packages",
                "label": "Manage Config Packages",
                "category": "Configuration",
                "description": "Import and manage configuration packages",
            },
            {
                "key": "view_settings",
                "label": "View Settings",
                "category": "Configuration",
                "description": "View system settings",
            },
            {
                "key": "edit_settings",
                "label": "Edit Settings",
                "category": "Configuration",
                "description": "Edit system settings",
            },
            # ==================== SUBSCRIPTION PERMISSIONS ====================
            {
                "key": "view_subscription",
                "label": "View Subscription",
                "category": "Subscription",
                "description": "View subscription status and plans",
            },
            {
                "key": "manage_subscription",
                "label": "Manage Subscription",
                "category": "Subscription",
                "description": "Manage subscription and billing",
            },
            # ==================== ADMINISTRATION PERMISSIONS ====================
            {
                "key": "all",
                "label": "All Permissions",
                "category": "Administration",
                "description": "Full system access - superuser privileges",
            },
            {
                "key": "system_admin",
                "label": "System Administrator",
                "category": "Administration",
                "description": "System administration privileges",
            },
            {
                "key": "view_audit_logs",
                "label": "View Audit Logs",
                "category": "Administration",
                "description": "View system audit logs",
            },
        ]

        return Response(permissions_data)


class UserSetupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing User Setup permissions.
    Allows administrators to control what users can see and do.
    """

    from authentication.serializers import UserSetupSerializer

    serializer_class = UserSetupSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["user__username", "user__email", "user__full_name", "notes"]
    ordering_fields = ["user__username", "created_at", "updated_at"]
    ordering = ["user__username"]

    def get_queryset(self):
        """Get all user setups with related user info, excluding debug_admin"""
        from authentication.models import UserSetup

        return UserSetup.objects.select_related("user").exclude(
            user__username="debug_admin"
        )

    @action(detail=False, methods=["get"], url_path="my-setup")
    def my_setup(self, request):
        """Get the current user's setup"""
        from authentication.models import UserSetup

        user_setup = UserSetup.get_or_create_for_user(request.user)
        serializer = self.get_serializer(user_setup)
        return Response(serializer.data)

    @action(detail=False, methods=["patch"], url_path="my-setup")
    def update_my_setup(self, request):
        """Update the current user's setup (limited fields)"""
        from authentication.models import UserSetup

        user_setup = UserSetup.get_or_create_for_user(request.user)

        # Only allow updating notes by the user themselves
        # Other fields should be updated by admins only
        allowed_fields = ["notes"]
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = self.get_serializer(user_setup, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reset_to_defaults(self, request, pk=None):
        """Reset a user's setup to default permissions"""
        from authentication.models import UserSetup

        user_setup = self.get_object()

        # Reset to default permissions
        user_setup.can_see_buying_price = True
        user_setup.can_see_profit_margin = True
        user_setup.can_see_item_cost = True
        user_setup.can_post_previous_dates = True
        user_setup.can_reverse_purchase_invoice = True
        user_setup.can_reverse_sales_invoice = True
        user_setup.can_view_only_their_sales = True
        user_setup.save()

        serializer = self.get_serializer(user_setup)
        return Response(
            {
                "message": "User setup reset to defaults successfully",
                "data": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def users_without_setup(self, request):
        """Get list of users who don't have a setup yet"""
        from authentication.models import UserSetup, CustomUser

        users_with_setup = UserSetup.objects.values_list("user_id", flat=True)
        users_without = CustomUser.objects.exclude(id__in=users_with_setup).values(
            "id", "username", "email", "full_name"
        )

        return Response(list(users_without))

    @action(detail=False, methods=["post"])
    def create_missing_setups(self, request):
        """Create user setups for all users who don't have one"""
        from authentication.models import UserSetup, CustomUser

        users_with_setup = UserSetup.objects.values_list("user_id", flat=True)
        users_without = CustomUser.objects.exclude(id__in=users_with_setup)

        created_count = 0
        for user in users_without:
            UserSetup.get_or_create_for_user(user)
            created_count += 1

        return Response(
            {
                "message": f"Created {created_count} user setup(s) successfully",
                "created_count": created_count,
            }
        )
