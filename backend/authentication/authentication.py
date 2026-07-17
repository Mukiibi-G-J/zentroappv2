from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context, get_tenant, get_public_schema_name
from django.conf import settings
from rest_framework_simplejwt.settings import api_settings
from company.models import Company
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

User = get_user_model()


def enforce_token_valid_after_or_raise(user, validated_token):
    """
    Reject access tokens issued before user.token_valid_after (admin/API force logout).
    """
    token_valid_after = getattr(user, "token_valid_after", None)
    if not token_valid_after:
        return
    token_iat = validated_token.get("iat")
    if token_iat is None:
        raise InvalidToken("Token missing issue time")
    if isinstance(token_iat, datetime):
        token_issued_at = token_iat
    else:
        token_issued_at = datetime.fromtimestamp(int(token_iat), tz=dt_timezone.utc)
    if timezone.is_naive(token_issued_at):
        token_issued_at = timezone.make_aware(token_issued_at, dt_timezone.utc)
    if token_issued_at < token_valid_after:
        raise InvalidToken("Session expired. Please login again.")


class JWTAuthenticationWithRevocationChecks(JWTAuthentication):
    """
    Same as SimpleJWT's JWTAuthentication, but rejects tokens invalidated via
    CustomUser.token_valid_after (admin force-logout must apply on every Bearer route).
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        enforce_token_valid_after_or_raise(user, validated_token)
        return (user, validated_token)


# Routes that should use main domain (no tenant context)
MAIN_DOMAIN_ROUTES = [
    "/company/check-company-exists/",
    "/company/create-company-account/",
    "/company/validate-company-name/",
    "/company/task-status/",
    "/company/payment-methods/create_payment_intent/",
    "/company/payment-methods/verify_payment/",
    "/home/on-boarding",
    "/home/on-boarding/",
    "/company/pricing-plans-v2/",
]


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that validates user and tenant existence on every request.
    This prevents tokens from deleted users or tenants from being used.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result

        # Check if this is a main domain route
        path = request.path_info
        is_main_domain_route = any(route in path for route in MAIN_DOMAIN_ROUTES)

        schema_name_claim = validated_token.get("schema_name")
        if schema_name_claim:
            with schema_context(schema_name_claim):
                if not User.objects.filter(
                    id=user.id, is_verified=True, is_active=True
                ).exists():
                    raise InvalidToken(
                        "User does not exist, is inactive, or is not verified"
                    )
        else:
            if not User.objects.filter(
                id=user.id, is_verified=True, is_active=True
            ).exists():
                raise InvalidToken(
                    "User does not exist, is inactive, or is not verified"
                )

        enforce_token_valid_after_or_raise(user, validated_token)

        # For main domain routes, skip tenant validation
        if not is_main_domain_route:
            # Explicitly check tenant/company exists and is active.
            # Company (TENANT_MODEL) rows live in the public schema; the connection may be
            # tenant-scoped, so always query Company from public.
            try:
                tenant = get_tenant(request)
                if not tenant:
                    raise InvalidToken("Tenant company does not exist or is inactive")
                public_schema = get_public_schema_name()
                with schema_context(public_schema):
                    if not Company.objects.filter(pk=tenant.pk).exists():
                        raise InvalidToken(
                            "Tenant company does not exist or is inactive"
                        )
            except InvalidToken:
                raise
            except Exception:
                raise InvalidToken("Tenant company does not exist or is inactive")

        return (user, validated_token)

    def get_user(self, validated_token):
        """
        Override to add user existence validation
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
            email_claim = validated_token.get("email")
            schema_name = validated_token.get("schema_name")

            def _email_matches_user(user_obj) -> bool:
                """Require exact email match only when the token carries a non-empty email."""
                if email_claim is None or email_claim == "":
                    return True
                u = (user_obj.email or "").strip().lower()
                c = str(email_claim).strip().lower()
                return bool(u) and u == c

            def _validate_loaded_user(user_obj):
                if not user_obj.is_verified:
                    raise InvalidToken("User account is not verified")
                if not user_obj.is_active:
                    raise InvalidToken("User account is inactive")
                if not _email_matches_user(user_obj):
                    raise InvalidToken("User no longer exists")
                return user_obj

            # For main domain routes, don't use schema context
            if schema_name:
                with schema_context(schema_name):
                    try:
                        user = User.objects.get(pk=user_id)
                    except User.DoesNotExist:
                        raise InvalidToken("User no longer exists")
                    return _validate_loaded_user(user)
            else:
                # Fallback for main domain routes without schema context
                try:
                    user = User.objects.get(pk=user_id)
                    return _validate_loaded_user(user)
                except User.DoesNotExist:
                    # For main domain routes, if user is not found in main domain,
                    # try to find them in their tenant schema
                    if email_claim:
                        # Try to find the user in any tenant schema
                        from django_tenants.utils import get_public_schema_name

                        public_schema = get_public_schema_name()

                        # Get all companies and try to find the user
                        from company.models import Company

                        companies = Company.objects.exclude(schema_name=public_schema)
                        needle = str(email_claim).strip().lower()

                        for company in companies:
                            try:
                                with schema_context(company.schema_name):
                                    user = User.objects.get(
                                        email__iexact=needle, is_verified=True
                                    )
                                    return user
                            except User.DoesNotExist:
                                continue

                    raise InvalidToken("User not found-------------------")

        except KeyError:
            raise InvalidToken("Token contains no recognizable user identification")
        except User.DoesNotExist:
            raise InvalidToken("User not found--------------")
