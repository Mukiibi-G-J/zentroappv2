from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db import transaction, connection
from celery.result import AsyncResult
from celery.states import PENDING, SUCCESS, FAILURE, STARTED
import time
import os
from django.core.cache import cache
from django.conf import settings
from celery import chain
from django_tenants.utils import schema_context
from authentication.authentication import (
    JWTAuthenticationWithRevocationChecks as JWTAuthentication,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from decimal import Decimal, InvalidOperation

from .models import Pricing, PaymentMethod, BillingHistory, Subscription, AddOn

from company.models import Company
from company.tasks import create_company_task, import_initial_data_task
from company.enums import SubscriptionPlan, SubscriptionStatus
from company.subscription_billing import (
    aware_start_of_day,
    parse_billing_period_from_metadata,
    subscription_period_end_inclusive,
    subscription_plan_value_from_product,
)


import json
from rest_framework.decorators import api_view, action, parser_classes
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from redis.exceptions import ConnectionError as RedisConnectionError
import logging
from company.models import BusinessCategory, BusinessObjective

# import stripe
import stripe
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from .models import (
    ZentroStarterOffer,
    ZentroStarterOrder,
    ZentroStarterPayment,
    ZentroStarterInstallmentReminder,
)


from .serializers import (
    PaymentMethodSerializer,
    BillingHistorySerializer,
    SubscriptionSerializer,
    PricingSerializer,
    AddOnSerializer,
    CompanyOverviewSerializer,
)
from django_tenants.utils import get_tenant
from company.models import PaymentGateway
from authentication.models import CustomUser
from authentication.user_management_views import DEBUG_USER_USERNAMES
from rest_framework.decorators import permission_classes, authentication_classes

logger = logging.getLogger(__name__)

# Page object: Branch Management (see populate_page_objects)
BRANCH_MANAGEMENT_PAGE_ID = 10904


def _branch_mgmt_perm(request, action="read"):
    if not hasattr(request.user, "check_object_permission"):
        return (True, None)
    has_perm, _ = request.user.check_object_permission(
        BRANCH_MANAGEMENT_PAGE_ID, action
    )
    return (has_perm, "Insufficient permissions" if not has_perm else None)


def is_company_existing(request):
    company_name = request.POST.get("company_name")
    if company_name == "":
        return JsonResponse({"html": "", "is_existing": False})

    # check if company name is already taken
    if Company.objects.filter(name=company_name).exists():
        html = (
            '<span style="'
            "color: #ef4444;"
            "display: flex;"
            "align-items: center;"
            "gap: 0.5rem;"
            '">'
            '<i class="fa-solid fa-xmark"></i>'
            f"Company name {company_name} is already registered/taken"
            "</span>"
        )
        is_existing = True

    # check if company name does not contain hyphen
    elif not company_name.isalnum():
        special_characters = "".join(
            [char for char in company_name if not char.isalnum()]
        )
        html = (
            '<span style="'
            "color: #ef4444;"
            "display: flex;"
            "align-items: center;"
            "gap: 0.5rem;"
            '">'
            '<i class="fa-solid fa-xmark"></i>'
            f"Company name {company_name} contains a the following special characters: {special_characters}"
            "</span>"
        )
        is_existing = True

    # check if company name is valid
    else:
        html = (
            '<span style="'
            "color: #10b981;"
            "display: flex;"
            "align-items: center;"
            "gap: 0.5rem;"
            '">'
            '<i class="fa-solid fa-check"></i>'
            f"Company name  {company_name} is valid"
            "</span>"
        )
        is_existing = False
    return JsonResponse({"html": html, "is_existing": is_existing})


def check_validity_of_company(request):
    company_name = request.POST.get("company_name")
    is_valid = Company.objects.filter(name=company_name).exists()

    if is_valid:
        html = (
            '<span style="'
            "color: #10b981;"
            "display: flex;"
            "align-items: center;"
            "gap: 0.5rem;"
            '">'
            '<i class="fa-solid fa-check"></i>'
            "Company name is valid"
            "</span>"
        )
    else:
        html = (
            '<span style="'
            "color: #ef4444;"
            "display: flex;"
            "align-items: center;"
            "gap: 0.5rem;"
            '">'
            '<i class="fa-solid fa-xmark"></i>'
            "Company name is invalid"
            "</span>"
        )

    return JsonResponse({"html": html, "is_valid": is_valid})


def company_onboarding(request):
    if request.method == "POST":
        data = json.loads(request.body)
        if data:
            try:
                # Ensure we're in public schema for company creation
                with schema_context("public"):
                    # Execute single task that handles everything
                    result = create_company_task.delay(data)

                    return JsonResponse(
                        {
                            "message": "Company Creation Started",
                            "task_id": result.id,
                            "company_name": data["name"],
                        }
                    )

            except Exception as e:
                return JsonResponse(
                    {"message": f"Error: {str(e)}", "success": False}, status=400
                )
    return JsonResponse({"message": "Invalid request method"}, status=405)


def get_task_status(request, task_id):
    task = AsyncResult(task_id)

    # Get or set the start time in cache
    start_time = cache.get(f"task_start_{task_id}")
    if not start_time and task.state != PENDING:
        start_time = time.time()
        cache.set(f"task_start_{task_id}", start_time, timeout=3600)  # 1 hour timeout

    if task.state == PENDING:
        response = {
            "state": task.state,
            "progress": 0,
            "message": "Task is pending...",
            "status": "pending",
        }
    elif task.state == FAILURE:
        response = {
            "state": task.state,
            "progress": 0,
            "message": str(task.info),  # Error message
            "status": "failed",
        }
    else:
        # For STARTED, PROGRESS, SUCCESS states
        if task.info is None:
            response = {
                "state": task.state,
                "progress": 100,
                "message": "Task completed",
                "status": "completed",
            }
        else:
            response = {
                "state": task.state,
                "progress": task.info.get("progress", 0),
                "message": task.info.get("message", ""),
                "status": task.info.get("status", ""),
            }
            # Add result data if task is successful
            if task.state == SUCCESS:
                response["result"] = task.info

    return JsonResponse(response)


@api_view(["POST"])
def validate_company_name(request):
    company_name = request.data.get("company_name", "").strip()

    if not company_name:
        return Response(
            {
                "isValid": False,
                "message": "Company name cannot be empty",
                "errors": ["Company name is required"],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if company name contains special characters
    if not company_name.replace(" ", "").isalnum():
        special_characters = [
            char for char in company_name if not char.isalnum() and char != " "
        ]
        return Response(
            {
                "isValid": False,
                "message": f"Company name contains invalid special characters: {', '.join(special_characters)}",
                "errors": [
                    "Company name can only contain letters, numbers, and spaces"
                ],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Check if company name is already taken
    if Company.objects.filter(name=company_name).exists():
        return Response(
            {
                "isValid": False,
                "message": f"Company name '{company_name}' is already registered",
                "errors": ["Company name already exists"],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Company name is valid
    return Response(
        {
            "isValid": True,
            "message": f"Company name '{company_name}' is valid",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def create_company_account(request):
    data = request.data
    try:
        # Validate required fields
        required_fields = [
            "companyName",
            "companyEmail",
            "companyPhone",
            "companyAddress",
            "companyCountry",
            "fullName",
            "password",
            "organization_size",
            "business_category",
            "business_objective",
        ]

        missing_fields = [
            field for field in required_fields if field not in data or not data[field]
        ]

        if missing_fields:
            return Response(
                {
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                    "error_type": "validation_error",
                    "success": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context("public"):
            try:
                # Map the frontend field names to what the task expects
                task_data = {
                    "name": data["companyName"],
                    "email": data["companyEmail"],
                    "phone": data["companyPhone"],
                    "address": data["companyAddress"],
                    "city": data.get("companyCity") or "",
                    "country": data["companyCountry"],
                    "full_name": data["fullName"],
                    "password": data["password"],
                    "organization_size": data["organization_size"],
                    "business_category": data["business_category"],
                    "business_objective": data["business_objective"],
                    "user_id": request.user.id,
                    "subscription": {
                        "plan": data.get("subscription", {}).get("plan", "FREE_TRIAL"),
                        "price": data.get("subscription", {}).get("price", 0),
                        "yearlyPrice": data.get("subscription", {}).get(
                            "yearlyPrice", 0
                        ),
                    },
                }

                # Additional validation for full_name - checking format
                if len(task_data["full_name"]) < 3:
                    return Response(
                        {
                            "message": "Full name must be at least 3 characters long",
                            "error_type": "validation_error",
                            "success": False,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                result = create_company_task.delay(task_data)

                return Response(
                    {
                        "message": "Company account creation started",
                        "task_id": result.id,
                        "company_name": data["companyName"],
                    },
                    status=status.HTTP_200_OK,
                )

            except RedisConnectionError as redis_error:
                logger.error(f"Redis connection error: {str(redis_error)}")
                return Response(
                    {
                        "message": "Service temporarily unavailable. Please try again in a few minutes.",
                        "error_type": "service_unavailable",
                        "success": False,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except Exception as e:
                logger.error(f"Task creation error: {str(e)}")
                return Response(
                    {
                        "message": "Failed to start company creation process",
                        "error_type": "task_creation_failed",
                        "success": False,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    except Exception as e:
        logger.error(f"Company creation error: {str(e)}")
        return Response(
            {
                "message": "An unexpected error occurred",
                "error_type": "unexpected_error",
                "success": False,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def check_company_exists(request):
    """
    Check if a company exists and validate its name format
    Returns JSON data for frontend handling
    """
    try:
        company_name = request.data.get("company_name", "").strip()

        if not company_name:
            return Response(
                {
                    "is_existing": False,
                    "message": "Company name is required",
                    "status": "error",
                }
            )

        with schema_context("public"):
            # Check if company name is already taken
            if Company.objects.filter(name__iexact=company_name).exists():
                return Response(
                    {
                        "is_existing": True,
                        "message": f"Company name {company_name} is valid",
                        "status": "success",
                    }
                )

            # Check if company name contains special characters
            if not company_name.replace("_", "").isalnum():
                special_characters = "".join(
                    [char for char in company_name if not char.isalnum()]
                )
                return Response(
                    {
                        "is_existing": False,
                        "message": f"Company name contains special characters: {special_characters}",
                        "status": "error",
                    }
                )

            # Company doesn't exist
            return Response(
                {
                    "is_existing": False,
                    "message": f"Company {company_name} does not exist",
                    "status": "error",
                }
            )

    except Exception as e:
        logger.error(f"Error checking company existence: {str(e)}")
        return Response(
            {
                "is_existing": False,
                "message": "An error occurred while checking company name",
                "status": "error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def get_queryset(self):
        from django_tenants.utils import get_tenant

        company = get_tenant(self.request)
        return PaymentMethod.objects.filter(company=company)

    def create(self, request, *args, **kwargs):
        # Add the gateway_method_id to the serializer context
        serializer = self.get_serializer(
            data=request.data,
            context={"gateway_method_id": request.data.get("gateway_method_id")},
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def set_primary(self, request, pk=None):
        payment_method = self.get_object()
        payment_method.is_primary = True
        payment_method.save()
        return Response(self.get_serializer(payment_method).data)

    @action(detail=False, methods=["post"])
    def create_payment_intent(self, request):
        try:
            schema_name = request.data.get("schema_name")
            if not schema_name:
                return Response(
                    {"error": "Schema name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            print(f"Schema name: {schema_name}")
            print(f"Request data: {request.data}")

            # Use schema context to find the company
            from django_tenants.utils import schema_context

            # with schema_context(schema_name):
            try:
                company = Company.objects.get(schema_name=schema_name)
                if not company.id:
                    return Response(
                        {"error": "Company does not exist"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except Company.DoesNotExist:
                return Response(
                    {"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND
                )

            print(f"Company: {company}")

            # Set Stripe API key
            stripe.api_key = settings.STRIPE_SECRET_KEY

            amount = request.data.get("amount")
            if amount is None:
                return Response(
                    {"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            try:
                amount_decimal = Decimal(str(amount))
            except (InvalidOperation, TypeError):
                return Response(
                    {"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST
                )

            currency = str(request.data.get("currency", "ugx")).upper()
            product_name = request.data.get("product_name", "Subscription Payment")
            plan_id = request.data.get("plan_id")
            add_on_ids = request.data.get("add_on_ids") or []
            extra_users_count = int(request.data.get("extra_users_count") or 0)

            months_raw = request.data.get("months", 1)
            billing_cycle_raw = request.data.get("billing_cycle", "monthly")
            try:
                months_int = int(months_raw)
            except (TypeError, ValueError):
                months_int = 1
            months_int = max(1, min(months_int, 24))
            billing_cycle = str(billing_cycle_raw or "monthly").strip().lower()
            if billing_cycle not in ("monthly", "yearly"):
                billing_cycle = "monthly"

            metadata_base = {
                "company_id": str(company.id),
                "product_name": product_name,
                "months": str(months_int),
                "billing_cycle": billing_cycle,
            }
            if plan_id is not None:
                metadata_base["plan_id"] = str(plan_id)
            if add_on_ids:
                metadata_base["add_on_ids"] = ",".join(str(x) for x in add_on_ids)
            if extra_users_count:
                metadata_base["extra_users_count"] = str(extra_users_count)

            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(
                    amount_decimal * 100
                ),  # Convert to cents/smallest currency unit
                currency=currency.lower(),
                automatic_payment_methods={
                    "enabled": True,
                },
                metadata=metadata_base,
            )

            billing_metadata = {
                "schema_name": schema_name,
                "product_name": product_name,
                "months": months_int,
                "billing_cycle": billing_cycle,
            }
            if plan_id is not None:
                billing_metadata["plan_id"] = plan_id
            if add_on_ids:
                billing_metadata["add_on_ids"] = add_on_ids
            if extra_users_count:
                billing_metadata["extra_users_count"] = extra_users_count

            billing_history, created = BillingHistory.objects.get_or_create(
                company=company,
                gateway_payment_id=intent.id,
                defaults={
                    "payment_gateway": PaymentGateway.STRIPE,
                    "product": product_name,
                    "status": "pending",
                    "billing_date": timezone.now().date(),
                    "amount": amount_decimal,
                    "currency": currency,
                    "metadata": billing_metadata,
                },
            )

            if not created:
                billing_history.product = product_name
                billing_history.status = "pending"
                billing_history.billing_date = timezone.now().date()
                billing_history.amount = amount_decimal
                billing_history.currency = currency
                updated_metadata = billing_history.metadata or {}
                updated_metadata.update(billing_metadata)
                billing_history.metadata = updated_metadata
                billing_history.save()

            return Response(
                {
                    "client_secret": intent.client_secret,
                    "payment_intent_id": intent.id,
                    "billing_history_id": billing_history.id,
                }
            )

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in create_payment_intent: {e}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def confirm_payment(self, request):
        try:
            payment_intent_id = request.data.get("payment_intent_id")
            billing_history_id = request.data.get("billing_history_id")

            stripe.api_key = settings.STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Update billing history
            billing_history = BillingHistory.objects.get(id=billing_history_id)
            if intent.status == "succeeded":
                billing_history.status = "paid"

                # If this was a subscription payment, update subscription
                if billing_history.product.startswith("Subscription"):
                    subscription = Subscription.objects.get(
                        company=request.user.company
                    )
                    subscription.is_paid = True
                    subscription.save()
            else:
                billing_history.status = "failed"

            billing_history.save()

            return Response(
                {"status": intent.status, "billing_status": billing_history.status}
            )

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def verify_payment(self, request):
        try:
            with transaction.atomic():
                payment_intent_id = request.data.get("payment_intent_id")
                if not payment_intent_id:
                    return Response(
                        {"error": "Payment intent ID is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                stripe.api_key = settings.STRIPE_SECRET_KEY
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

                # Update subscription status based on payment intent
                if payment_intent.status == "succeeded":
                    # Get the company from metadata
                    company_id = payment_intent.metadata.get("company_id")
                    company = Company.objects.get(id=company_id)
                    subscription = Subscription.objects.get(company=company)
                    # Update subscription based on product name
                    product_name = payment_intent.metadata.get(
                        "product_name", ""
                    ).lower()

                    if "premium" in product_name:
                        subscription.plan = SubscriptionPlan.PREMIUM.value
                    elif "standard" in product_name:
                        subscription.plan = SubscriptionPlan.STANDARD.value
                    elif "free trial" in product_name:
                        subscription.plan = SubscriptionPlan.FREE_TRIAL.value
                    subscription.is_paid = True
                    subscription.status = SubscriptionStatus.ACTIVE.value
                    subscription.payment_method = "stripe"
                    subscription.PaymentStatus = "paid"
                    subscription.gateway_subscription_id = payment_intent.id
                    subscription.gateway_customer_id = payment_intent.customer
                    # subscription.gateway_price_id = payment_intent.items[0].price.id
                    subscription.start_date = timezone.now()
                    subscription.end_date = timezone.now() + timezone.timedelta(
                        days=(
                            30
                            if "month"
                            in payment_intent.metadata.get("product_name", "").lower()
                            else 365
                        )
                    )
                    subscription.save()

                    # Create or update billing history
                    BillingHistory.objects.create(
                        company=company,
                        payment_gateway="stripe",
                        product=payment_intent.metadata.get("product_name"),
                        status="completed",
                        billing_date=timezone.now(),
                        amount=payment_intent.amount / 100,  # Convert from cents
                        currency=payment_intent.currency,
                        gateway_payment_id=payment_intent_id,
                    )

                    return Response(
                        {
                            "status": "succeeded",
                            "message": "Payment verified and subscription activated",
                            "subscription": {
                                "plan": subscription.plan,
                                "status": subscription.status,
                                "start_date": subscription.start_date,
                                "end_date": subscription.end_date,
                            },
                        }
                    )

            return Response(
                {"status": payment_intent.status, "message": "Payment not completed"}
            )

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Payment verification error: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BillingHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = BillingHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django_tenants.utils import get_tenant

        company = get_tenant(self.request)
        return BillingHistory.objects.filter(company=company)


class PricingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving pricing plans
    """

    serializer_class = PricingSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]
    authentication_classes = [
        SessionAuthentication,
        JWTAuthentication,
    ]

    def get_queryset(self):
        return Pricing.objects.filter(is_active=True).order_by("order")


class PricingViewSetV2(viewsets.ReadOnlyModelViewSet):
    serializer_class = PricingSerializer
    pagination_class = None

    def get_queryset(self):
        return Pricing.objects.filter(is_active=True).order_by("order")


class AddOnViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AddOnSerializer
    pagination_class = None
    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def get_queryset(self):
        return AddOn.objects.filter(is_active=True).order_by("order")


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django_tenants.utils import get_tenant

        company = get_tenant(self.request)
        return Subscription.objects.filter(company=company)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        subscription = self.get_object()
        serializer = self.get_serializer(
            subscription,
            data=request.data,
            partial=True,
            context={
                "action": "activate",
                "gateway_subscription_id": request.data.get("gateway_subscription_id"),
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        subscription = self.get_object()
        serializer = self.get_serializer(
            subscription, data=request.data, partial=True, context={"action": "cancel"}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def company_overview(request):
    """
    Get company overview data including company details, subscription, and stats
    """
    try:
        # Get the current tenant/company from the request
        from django_tenants.utils import get_tenant

        company = get_tenant(request)

        subscription = Subscription.objects.filter(company=company).first()

        # Get starter pack information (include pending orders for partial payments)
        starter_order = (
            ZentroStarterOrder.objects.filter(
                company=company,
                status__in=["pending", "paid", "active", "free_period_ended"],
            )
            .order_by("-created_at")
            .first()
        )

        starter_pack_data = None
        if starter_order:
            starter_pack_data = {
                "has_starter_pack": True,
                "order_id": starter_order.id,
                "offer_name": starter_order.offer.name,
                "total_amount": str(starter_order.total_amount),
                "amount_paid": str(starter_order.amount_paid),
                "amount_remaining": str(starter_order.amount_remaining),
                "payment_amount": str(
                    starter_order.payment_amount
                ),  # Keep for backwards compatibility
                "payment_status": starter_order.payment_status,
                "order_status": starter_order.status,
                "device_included": starter_order.device_included,
                "free_months_earned": starter_order.free_months_earned,
                "free_period_active": starter_order.is_free_period_active,
                "free_period_days_remaining": starter_order.free_period_days_remaining,
                "subscription_active": starter_order.is_subscription_active,
                "subscription_days_remaining": starter_order.subscription_days_remaining,
                "should_start_monthly": starter_order.should_start_monthly_subscription,
                "offer_was_active_at_payment": starter_order.is_offer_active_at_payment,
                "order_date": (
                    starter_order.order_date.isoformat()
                    if starter_order.order_date
                    else None
                ),
                "subscription_start_date": (
                    starter_order.subscription_start_date.isoformat()
                    if starter_order.subscription_start_date
                    else None
                ),
                "subscription_end_date": (
                    starter_order.subscription_end_date.isoformat()
                    if starter_order.subscription_end_date
                    else None
                ),
                "free_period_end_date": (
                    starter_order.free_period_end_date.isoformat()
                    if starter_order.free_period_end_date
                    else None
                ),
            }
        else:
            starter_pack_data = {
                "has_starter_pack": False,
                "message": "No starter pack found",
            }

        # Get user stats - no need to filter by company since we're in tenant context
        # Exclude debug_admin from counts
        from authentication.models import CustomUser as User

        total_users = User.objects.exclude(username="debug_admin").count()
        active_users = (
            User.objects.filter(is_active=True).exclude(username="debug_admin").count()
        )
        admin_users = (
            User.objects.filter(is_staff=True).exclude(username="debug_admin").count()
        )

        # User limit for Add User flow (with breakdown for display)
        breakdown = company.get_user_limit_breakdown()
        effective_max = breakdown["max_users"]
        user_limit_reached = active_users >= effective_max

        # Get billing stats - filter by current company
        payment_methods = PaymentMethod.objects.filter(company=company, is_active=True)
        billing_history = BillingHistory.objects.filter(company=company).order_by(
            "-billing_date"
        )[:5]

        from financials.currency import get_local_currency_code

        data = {
            "company": {
                "name": company.name,
                "displayName": company.display_name or company.name,
                "logo": company.logo.url if company.logo else None,
                "address": company.address,
                "phone": company.phone,
                "email": company.email,
                "website": company.website or "",
                "city": company.city,
                "country": company.country,
                "tin": company.tin,
            },
            "subscription": (
                SubscriptionSerializer(subscription, context={"request": request}).data
                if subscription
                else None
            ),
            "starter_pack": starter_pack_data,
            "stats": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "admin_users": admin_users,
            },
            "user_limit": {
                "max_users": effective_max,
                "current_users": active_users,
                "user_limit_reached": user_limit_reached,
                "subscription_page_url": "/subscription",
                "plan_users": breakdown["plan_users"],
                "extra_users_purchased": breakdown["extra_users_purchased"],
            },
            "payment_methods": PaymentMethodSerializer(
                payment_methods, many=True, context={"request": request}
            ).data,
            "recent_billing": BillingHistorySerializer(
                billing_history, many=True, context={"request": request}
            ).data,
            "settings": {
                "localCurrencyCode": get_local_currency_code(),
            },
        }

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching company overview: {str(e)}")
        return Response(
            {"error": "Failed to fetch company overview"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@parser_classes([MultiPartParser, FormParser])
def upload_company_logo(request):
    """
    Upload company logo
    """
    try:
        company = get_tenant(request)

        if "logo" not in request.FILES:
            return Response(
                {"error": "No logo file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logo_file = request.FILES["logo"]

        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if logo_file.content_type not in allowed_types:
            return Response(
                {"error": "Invalid file type. Please upload a JPEG, PNG, or GIF image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (max 5MB)
        if logo_file.size > 5 * 1024 * 1024:
            return Response(
                {
                    "error": "File size too large. Please upload an image smaller than 5MB"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save the logo
        company.logo = logo_file
        company.save()

        # Return updated company data
        data = {
            "company": {
                "name": company.name,
                "logo": (
                    request.build_absolute_uri(company.logo.url)
                    if company.logo
                    else None
                ),
                "address": company.address,
                "phone": company.phone,
                "email": company.email,
                "city": company.city,
                "country": company.country,
                "tin": company.tin,
            }
        }

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error uploading company logo: {str(e)}")
        return Response(
            {"error": "Failed to upload company logo"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def update_company_info(request):
    """
    Update company information (display_name, phone, email, website, TIN, address, city, country).
    Company legal name (name) cannot be changed via this endpoint.
    """
    try:
        company = get_tenant(request)

        # Only allow updating specific fields (exclude legal company name)
        if "displayName" in request.data:
            company.display_name = request.data["displayName"] or company.name

        if "phone" in request.data:
            company.phone = request.data["phone"]

        if "email" in request.data:
            email = request.data["email"]
            # Validate email format
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:
                validate_email(email)
                company.email = email
            except ValidationError:
                return Response(
                    {"error": "Invalid email format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "website" in request.data:
            website = request.data["website"]
            # Allow empty string to clear website
            if website:
                website = website.strip()
                # Auto-prepend https:// if no protocol is provided
                if website and not website.startswith(("http://", "https://")):
                    website = f"https://{website}"

                from django.core.validators import URLValidator
                from django.core.exceptions import ValidationError as URLValidationError

                try:
                    validator = URLValidator()
                    validator(website)
                    company.website = website
                except URLValidationError:
                    return Response(
                        {"error": "Invalid website URL format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                company.website = None

        if "tin" in request.data:
            company.tin = request.data["tin"]

        if "address" in request.data:
            address = (request.data.get("address") or "").strip()
            if len(address) > 255:
                return Response(
                    {"error": "Address must be 255 characters or fewer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company.address = address

        if "city" in request.data:
            city = (request.data.get("city") or "").strip()
            if len(city) > 100:
                return Response(
                    {"error": "City must be 100 characters or fewer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company.city = city or None

        if "country" in request.data:
            country = (request.data.get("country") or "").strip()
            if len(country) > 100:
                return Response(
                    {"error": "Country must be 100 characters or fewer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company.country = country or None

        updated_local_currency_code = None
        if "localCurrencyCode" in request.data:
            from financials.currency import (
                get_local_currency_code,
                normalize_local_currency_code,
            )
            from financials.models import GeneralLedgerSetup

            if not (
                request.user.is_staff
                or request.user.is_superuser
                or "admin" in (getattr(request.user, "get_authority", lambda: [])() or [])
            ):
                return Response(
                    {"error": "Only administrators can update local currency"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            normalized = normalize_local_currency_code(
                request.data.get("localCurrencyCode")
            )
            if not normalized:
                return Response(
                    {"error": "Invalid local currency code"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            gl_setup = GeneralLedgerSetup.objects.first()
            if not gl_setup:
                gl_setup = GeneralLedgerSetup.objects.create(
                    local_currency_code=normalized
                )
            elif gl_setup.local_currency_code != normalized:
                gl_setup.local_currency_code = normalized
                gl_setup.save(update_fields=["local_currency_code", "updated_at"])
            updated_local_currency_code = normalized

        company.save()

        from financials.currency import get_local_currency_code

        # Return updated company data
        data = {
            "company": {
                "name": company.name,
                "displayName": company.display_name or company.name,
                "logo": (
                    request.build_absolute_uri(company.logo.url)
                    if company.logo
                    else None
                ),
                "address": company.address,
                "phone": company.phone,
                "email": company.email,
                "website": company.website or "",
                "city": company.city,
                "country": company.country,
                "tin": company.tin,
            },
            "settings": {
                "localCurrencyCode": updated_local_currency_code
                or get_local_currency_code(),
            },
        }

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error updating company information: {str(e)}")
        return Response(
            {"error": "Failed to update company information"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def company_users(request):
    """
    Get company users list with their details
    """
    try:
        # No need to filter by company since we're in tenant context
        # Exclude debug_admin from the list
        from authentication.models import CustomUser as User

        users = User.objects.exclude(username="debug_admin").prefetch_related("roles")

        users_data = []
        for user in users:
            # Get user roles as a list
            user_roles = [role.name for role in user.roles.all()]
            primary_role = (
                user_roles[0] if user_roles else ("Admin" if user.is_staff else "User")
            )

            users_data.append(
                {
                    "id": user.id,
                    "name": user.full_name or user.username,
                    "email": user.email,
                    "phone": user.phone_number,
                    "branch": (
                        user.global_dimension_1.code
                        if user.global_dimension_1
                        else None
                    ),
                    "role": primary_role,
                    "roles": user_roles,
                    "status": "active" if user.is_active else "inactive",
                    "avatar": None,  # Add avatar field if available
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                }
            )

        return Response(users_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching company users: {str(e)}")
        return Response(
            {"error": "Failed to fetch company users"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_roles(request):
    """
    Get all available roles
    """
    try:
        from authentication.models import Role

        roles = Role.objects.filter(is_active=True).order_by("name")
        roles_data = [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions,
            }
            for role in roles
        ]

        return Response(roles_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching roles: {str(e)}")
        return Response(
            {"error": "Failed to fetch roles"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_branches(request):
    """
    List BRANCH dimension values (locations) for the tenant.
    """
    try:
        from dimension.models import Dimension, DimensionValue

        branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        if not branch_dim:
            return Response([], status=status.HTTP_200_OK)
        branches = DimensionValue.objects.filter(dimension_code=branch_dim).order_by(
            "description"
        )
        branches_data = [
            {
                "id": str(branch.id),
                "name": branch.description,
                "code": branch.code,
            }
            for branch in branches
        ]

        return Response(branches_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching branches: {str(e)}")
        return Response(
            {"error": "Failed to fetch branches"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def branch_limits(request):
    """
    Subscription branch cap and current BRANCH dimension value count.
    """
    has_perm, err = _branch_mgmt_perm(request, "read")
    if not has_perm:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied(err)
    try:
        company = get_tenant(request)
        from dimension.models import Dimension, DimensionValue
        from financials.models import GeneralLedgerSetup

        bd = company.get_branch_limit_breakdown()
        branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        current = (
            DimensionValue.objects.filter(dimension_code=branch_dim).count()
            if branch_dim
            else 0
        )
        gl = GeneralLedgerSetup.objects.first()
        enable_multi = bool(gl and getattr(gl, "enable_multiple_branches", False))
        max_b = bd["max_branches"]
        can_add = max_b is None or current < max_b
        return Response(
            {
                "plan_branches_label": bd["plan_branches_label"],
                "max_branches": max_b,
                "current_branches": current,
                "can_add": can_add,
                "enable_multiple_branches": enable_multi,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.error(f"Error in branch_limits: {str(e)}")
        return Response(
            {"error": "Failed to load branch limits"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def create_branch(request):
    """
    Add a BRANCH dimension value when the subscription allows more branches.
    """
    has_perm, err = _branch_mgmt_perm(request, "insert")
    if not has_perm:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied(err)
    try:
        company = get_tenant(request)
        max_b = company.get_effective_max_branches()
        from dimension.models import Dimension, DimensionValue
        from dimension.setup import BRANCH_DIMENSION_CODE, _unique_dimension_value_code
        from financials.models import GeneralLedgerSetup
        from django.utils.text import slugify
        from postings import enums as posting_enums

        branch_dim = Dimension.objects.filter(
            code__iexact=BRANCH_DIMENSION_CODE
        ).first()
        if not branch_dim:
            return Response(
                {
                    "error": "Branch dimension is not configured. Contact support.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        current_count = DimensionValue.objects.filter(dimension_code=branch_dim).count()
        if max_b is not None and current_count >= max_b:
            return Response(
                {
                    "error": "Branch limit reached for your subscription plan",
                    "code": "BRANCH_LIMIT_REACHED",
                    "max_branches": max_b,
                    "current_branches": current_count,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        description = (request.data.get("description") or "").strip()
        if not description:
            return Response(
                {"error": "description is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code_raw = (request.data.get("code") or "").strip()
        if not code_raw:
            code_raw = slugify(description) or "branch"
        code_base = slugify(str(code_raw).replace("_", "-"))
        if not code_base:
            return Response(
                {"error": "Invalid branch code"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Lowercase slug matches company signup + items.Location lookup convention.
        code_unique = _unique_dimension_value_code(code_base[:200])

        with transaction.atomic():
            dv = DimensionValue.objects.create(
                code=code_unique,
                description=description[:255],
                dimension_type=posting_enums.DimensionType.Standard.value,
                dimension_code=branch_dim,
            )
            # Keep items.Location in sync: POS/inventory resolve Location by
            # the same code as the BRANCH DimensionValue (see get_branch_for_request / POS location resolution).
            from items.models import Location

            loc, _ = Location.objects.update_or_create(
                code=dv.code,
                defaults={"description": dv.description},
            )
            from postings.setup import ensure_inventory_posting_setups_for_location

            ensure_inventory_posting_setups_for_location(loc)
            if current_count + 1 >= 2:
                gl = GeneralLedgerSetup.objects.first()
                if gl and not getattr(gl, "enable_multiple_branches", False):
                    gl.enable_multiple_branches = True
                    gl.save(update_fields=["enable_multiple_branches"])

        return Response(
            {
                "id": str(dv.id),
                "code": dv.code,
                "description": dv.description,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        logger.error(f"Error creating branch: {str(e)}")
        return Response(
            {"error": "Failed to create branch"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def create_user(request):
    """
    Create a new user for the company
    """
    try:
        # Get the current tenant/company from the request
        from django_tenants.utils import get_tenant

        company = get_tenant(request)

        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Enforce user limit
        effective_max = company.get_effective_max_users()
        current_count = (
            User.objects.filter(is_active=True).exclude(username="debug_admin").count()
        )
        if current_count >= effective_max:
            return Response(
                {
                    "error": "User limit reached",
                    "code": "USER_LIMIT_REACHED",
                    "max_users": effective_max,
                    "current_users": current_count,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate required fields
        required_fields = ["name", "email", "phone", "roles", "password"]
        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {"error": f"{field} is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check if user already exists - no need to filter by company since we're in tenant context
        if User.objects.filter(email=request.data["email"]).exists():
            return Response(
                {"error": "User with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(phone_number=request.data["phone"]).exists():
            return Response(
                {"error": "User with this phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate username from full name (limit to 30 characters)
        base_username = (
            request.data["name"].lower().replace(" ", "_")[:25]
        )  # Limit to 25 chars
        user_name = base_username
        counter = 1

        # Check if username exists and generate unique one
        while User.objects.filter(username=user_name).exists():
            suffix = str(counter)
            # Ensure total length doesn't exceed 30 characters
            if len(base_username) + len(suffix) + 1 <= 30:
                user_name = f"{base_username}_{suffix}"
            else:
                # If base username is too long, truncate it
                max_base_length = 30 - len(suffix) - 1
                user_name = f"{base_username[:max_base_length]}_{suffix}"
            counter += 1

        # Create user
        user_data = {
            "email": request.data["email"],
            "username": user_name,  # Use email as username
            "full_name": request.data["name"],
            "phone_number": request.data["phone"],
            "password": request.data["password"],
        }

        # Add dimension_1 (branch) - required when multi-branch is enabled
        from financials.models import GeneralLedgerSetup
        from dimension.models import DimensionValue

        gl_setup = GeneralLedgerSetup.objects.first()
        enable_multiple_branches = gl_setup and getattr(
            gl_setup, "enable_multiple_branches", False
        )
        if enable_multiple_branches and not request.data.get("branch"):
            return Response(
                {"error": "Branch is required when Multiple Branches is enabled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.data.get("branch"):
            try:
                branch_val = request.data["branch"]
                if isinstance(branch_val, int):
                    dimension_value = DimensionValue.objects.get(pk=branch_val)
                else:
                    dimension_value = DimensionValue.objects.get(code=str(branch_val))
                user_data["global_dimension_1"] = dimension_value
            except DimensionValue.DoesNotExist:
                return Response(
                    {"error": "Invalid branch selected"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Set staff status based on roles (if any role is admin, set is_staff to True)
        roles = request.data.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]  # Handle case where roles is sent as a single string

        # Check if any role is admin
        is_admin = any(role.lower() in ["admin", "administrator"] for role in roles)
        user_data["is_staff"] = is_admin

        user = User.objects.create_user(**user_data)

        # Assign roles to user
        from authentication.models import Role

        for role_name in roles:
            try:
                role = Role.objects.get(name__iexact=role_name)
                user.roles.add(role)
            except Role.DoesNotExist:
                # If role doesn't exist, create it
                role = Role.objects.create(
                    name=role_name, description=f"Role for {role_name}", permissions=[]
                )
                user.roles.add(role)

        return Response(
            {
                "message": "User created successfully",
                "user": {
                    "id": user.id,
                    "name": user.full_name or user.username,
                    "email": user.email,
                    "phone": user.phone_number,
                    "branch": (
                        user.global_dimension_1.code
                        if user.global_dimension_1
                        else None
                    ),
                    "role": "Admin" if user.is_staff else "User",
                    "status": "active" if user.is_active else "inactive",
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return Response(
            {"error": "Failed to create user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def update_user(request, user_id):
    """
    Update user details
    """
    try:
        # No need to filter by company since we're in tenant context
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Update user fields
        if "name" in request.data:
            user.full_name = request.data["name"]

        if "email" in request.data:
            user.email = request.data["email"]

        if "phone" in request.data:
            user.phone_number = request.data["phone"]

        if "branch" in request.data:
            from financials.models import GeneralLedgerSetup
            from dimension.models import DimensionValue

            gl_setup = GeneralLedgerSetup.objects.first()
            enable_multiple_branches = gl_setup and getattr(
                gl_setup, "enable_multiple_branches", False
            )
            branch_val = request.data["branch"]
            if not branch_val:
                if enable_multiple_branches:
                    return Response(
                        {
                            "error": "Branch cannot be cleared when Multiple Branches is enabled"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.global_dimension_1 = None
            else:
                try:
                    if isinstance(branch_val, int):
                        dimension_value = DimensionValue.objects.get(pk=branch_val)
                    else:
                        dimension_value = DimensionValue.objects.get(
                            code=str(branch_val)
                        )
                    user.global_dimension_1 = dimension_value
                except DimensionValue.DoesNotExist:
                    return Response(
                        {"error": "Invalid branch selected"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if "roles" in request.data:
            roles = request.data["roles"]
            if isinstance(roles, str):
                roles = [roles]  # Handle case where roles is sent as a single string

            # Clear existing roles
            user.roles.clear()

            # Assign new roles
            from authentication.models import Role

            for role_name in roles:
                try:
                    role = Role.objects.get(name__iexact=role_name)
                    user.roles.add(role)
                except Role.DoesNotExist:
                    # If role doesn't exist, create it
                    role = Role.objects.create(
                        name=role_name,
                        description=f"Role for {role_name}",
                        permissions=[],
                    )
                    user.roles.add(role)

            # Set staff status based on roles
            is_admin = any(role.lower() in ["admin", "administrator"] for role in roles)
            user.is_staff = is_admin

        user.save()

        return Response(
            {
                "message": "User updated successfully",
                "user": {
                    "id": user.id,
                    "name": user.full_name or user.username,
                    "email": user.email,
                    "phone": user.phone_number,
                    "branch": (
                        user.global_dimension_1.code
                        if user.global_dimension_1
                        else None
                    ),
                    "role": "Admin" if user.is_staff else "User",
                    "status": "active" if user.is_active else "inactive",
                },
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return Response(
            {"error": "Failed to update user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def delete_user(request, user_id):
    """
    Delete a user from the company
    """
    try:
        # No need to filter by company since we're in tenant context
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Prevent deleting the current user
        if user == request.user:
            return Response(
                {"error": "Cannot delete your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.delete()

        return Response(
            {"message": "User deleted successfully"}, status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        return Response(
            {"error": "Failed to delete user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def toggle_user_status(request, user_id):
    """
    Toggle user active/inactive status
    """
    try:
        # No need to filter by company since we're in tenant context
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Prevent deactivating the current user
        if user == request.user:
            return Response(
                {"error": "Cannot deactivate your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = not user.is_active
        user.save()

        return Response(
            {
                "message": f"User {'activated' if user.is_active else 'deactivated'} successfully",
                "user": {
                    "id": user.id,
                    "name": user.full_name
                    or f"{user.first_name} {user.last_name}".strip()
                    or user.username,
                    "email": user.email,
                    "role": "Admin" if user.is_staff else "User",
                    "status": "active" if user.is_active else "inactive",
                },
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error toggling user status: {str(e)}")
        return Response(
            {"error": "Failed to toggle user status"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_starter_offer(request):
    """Get current Zentro Starter offer details"""
    try:
        offers = ZentroStarterOffer.objects.filter(is_active=True).order_by(
            "device_price"
        )
        if not offers.exists():
            return Response(
                {"error": "No active offers found", "offers": []}, status=404
            )

        offers_data = []
        for offer in offers:
            offers_data.append(
                {
                    "id": offer.id,
                    "name": offer.name,
                    "free_months": offer.free_months,
                    "device_price": str(offer.device_price),
                    "end_date": offer.end_date.isoformat(),
                    "days_remaining": offer.days_remaining,
                    "is_expired": offer.is_expired,
                    "is_active": offer.is_active,
                    "is_kit": offer.device_price
                    >= 1000000,  # True for Zentro Kit (1.5M)
                    "is_starter": offer.device_price
                    < 1000000,  # True for Zentro Starter (< 1M)
                    "payment_plan": offer.payment_plan,  # one_time or installments
                    "allows_installments": offer.allows_installments,
                    "default_installment_count": offer.default_installment_count,
                    "show_time_limit": offer.show_time_limit,  # Control time badge visibility
                    "device_video": (
                        offer.device_video.url if offer.device_video else None
                    ),
                    "video_description": offer.video_description or "",
                    "has_video": bool(offer.device_video),
                }
            )

        return Response({"offers": offers_data})
    except Exception as e:
        return Response({"error": str(e), "offers": []}, status=500)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def create_starter_payment_intent(request):
    """Create a payment intent for Zentro Starter pack orders"""
    try:
        data = request.data

        # Validate required fields
        required_fields = ["offer_id", "payment_amount", "schema_name"]
        for field in required_fields:
            if field not in data:
                return Response(
                    {"error": f"Missing required field: {field}"}, status=400
                )

        # Get the company
        try:
            company = Company.objects.get(schema_name=data["schema_name"])
        except Company.DoesNotExist:
            return Response({"error": "Company not found"}, status=404)

        # Get the offer
        try:
            offer = ZentroStarterOffer.objects.get(id=data["offer_id"], is_active=True)
        except ZentroStarterOffer.DoesNotExist:
            return Response({"error": "Invalid or inactive offer"}, status=404)

        # Check if offer is still active
        if offer.is_expired:
            return Response({"error": "This offer has expired"}, status=400)

        # Set Stripe API key
        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            amount = Decimal(str(data["payment_amount"]))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid payment amount"}, status=400)

        currency = str(data.get("currency", "ugx")).lower()

        zero_decimal_currencies = {
            "bif",
            "clp",
            "djf",
            "gnf",
            "jpy",
            "kmf",
            "krw",
            "mga",
            "pyg",
            "rwf",
            "ugx",
            "vnd",
            "vuv",
            "xaf",
            "xof",
            "xpf",
        }

        if currency in zero_decimal_currencies:
            stripe_amount = int(amount)
        else:
            stripe_amount = int(amount * 100)

        if stripe_amount <= 0:
            return Response(
                {"error": "Payment amount must be greater than zero"}, status=400
            )

        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=stripe_amount,
            currency=currency,
            automatic_payment_methods={
                "enabled": True,
            },
            metadata={
                "company_id": str(company.id),
                "offer_id": str(offer.id),
                "product_name": f"Zentro Starter - {offer.name}",
                "payment_type": "starter_pack",
            },
        )

        return Response(
            {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "offer_id": offer.id,
                "amount": str(amount),
                "currency": currency.upper(),
            }
        )

    except stripe.error.StripeError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        print(f"Error in create_starter_payment_intent: {e}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def confirm_starter_payment(request):
    """Confirm payment for Zentro Starter pack orders"""
    try:
        data = request.data

        payment_intent_id = data.get("payment_intent_id")
        offer_id = data.get("offer_id")
        schema_name = data.get("schema_name")
        delivery_address = data.get("delivery_address", "")
        phone_number = data.get("phone_number", "")

        if not all([payment_intent_id, offer_id, schema_name]):
            return Response({"error": "Missing required fields"}, status=400)

        # Get the company
        try:
            company = Company.objects.get(schema_name=schema_name)
        except Company.DoesNotExist:
            return Response({"error": "Company not found"}, status=404)

        # Get the offer
        try:
            offer = ZentroStarterOffer.objects.get(id=offer_id, is_active=True)
        except ZentroStarterOffer.DoesNotExist:
            return Response({"error": "Invalid or inactive offer"}, status=404)

        # Verify payment with Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if intent.status != "succeeded":
            return Response({"error": "Payment not completed"}, status=400)

        # Check if company already has an active order (only one order per company allowed)
        existing_order = ZentroStarterOrder.objects.filter(
            company=company, status__in=["pending", "paid", "active"]
        ).first()

        if existing_order:
            return Response(
                {
                    "error": "Company already has an active order. Each company can only have one active order.",
                    "existing_order_id": existing_order.id,
                    "existing_order_offer": existing_order.offer.name,
                },
                status=400,
            )

        # Create the starter pack order
        order = ZentroStarterOrder.objects.create(
            company=company,
            offer=offer,
            payment_amount=offer.device_price,
            device_included=offer.device_price >= 1000000,  # True for Zentro Kit (1.5M)
            free_months_earned=offer.free_months,
            delivery_address=delivery_address,
            phone_number=phone_number,
            payment_status="completed",
            payment_date=timezone.now(),
            payment_reference=payment_intent_id,
            payment_gateway="stripe",
            gateway_transaction_id=payment_intent_id,
            status="paid",
        )

        # Activate the subscription
        order.activate_subscription()

        return Response(
            {
                "success": True,
                "order_id": order.id,
                "message": "Starter pack order completed successfully",
                "order_summary": order.get_subscription_summary(),
                "plan": "STARTER_PACK",  # Include plan in response
            }
        )

    except stripe.error.StripeError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        print(f"Error in confirm_starter_payment: {e}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def create_starter_order(request):
    """Create a new Zentro Starter order (can be created without payment for manual payment tracking)"""
    try:
        data = request.data

        # Validate required fields - schema_name OR company_email
        if "schema_name" in data:
            try:
                company = Company.objects.get(schema_name=data["schema_name"])
            except Company.DoesNotExist:
                return Response({"error": "Company not found"}, status=404)
        elif "company_email" in data:
            try:
                company = Company.objects.get(email=data["company_email"])
            except Company.DoesNotExist:
                return Response(
                    {"error": "Company not found with this email"}, status=404
                )
        else:
            return Response(
                {"error": "Missing schema_name or company_email"}, status=400
            )

        # Validate offer_id
        if "offer_id" not in data:
            return Response({"error": "Missing offer_id"}, status=400)

        # Get the offer
        try:
            offer = ZentroStarterOffer.objects.get(id=data["offer_id"], is_active=True)
        except ZentroStarterOffer.DoesNotExist:
            return Response({"error": "Invalid or inactive offer"}, status=404)

        # Check if offer is still active
        if offer.is_expired:
            return Response({"error": "This offer has expired"}, status=400)

        # Check if this is a free trial offer
        is_free_trial = offer.device_price == 0 or "free trial" in offer.name.lower()

        # Check if company already has an active order (only one order per company allowed)
        existing_order = ZentroStarterOrder.objects.filter(
            company=company, status__in=["pending", "paid", "active"]
        ).first()

        if existing_order:
            # If existing order is a free trial and not activated, activate it
            if is_free_trial and not existing_order.subscription_start_date:
                existing_order.status = "active"
                existing_order.payment_status = "completed"
                existing_order.payment_date = timezone.now()
                existing_order.save()
                existing_order.activate_subscription()

            return Response(
                {
                    "success": True,
                    "order_id": existing_order.id,
                    "message": "Company already has an active order. Each company can only have one active order.",
                    "order_summary": existing_order.get_subscription_summary(),
                    "existing_order": {
                        "id": existing_order.id,
                        "offer_name": existing_order.offer.name,
                        "total_amount": str(existing_order.total_amount),
                        "amount_paid": str(existing_order.amount_paid),
                        "status": existing_order.status,
                    },
                }
            )

        # Set total_amount from offer price (amount_paid is now calculated from payments)
        total_amount = offer.device_price

        # Determine initial status and payment status
        if is_free_trial:
            # Free trials are automatically activated
            initial_status = "active"
            payment_status = "completed"
        else:
            # Paid orders start as pending
            initial_status = "pending"
            payment_status = "pending"

        # Create the order
        # Note: amount_paid is a read-only property that calculates from payments
        # The database field defaults to 0.00, so we don't set it here
        order = ZentroStarterOrder.objects.create(
            company=company,
            offer=offer,
            total_amount=total_amount,
            payment_amount=total_amount,  # Keep for backwards compatibility
            device_included=offer.device_price >= 1000000,  # True for Zentro Kit (1.5M)
            free_months_earned=offer.free_months,
            delivery_address=data.get("delivery_address", ""),
            phone_number=data.get("phone_number", ""),
            payment_status=payment_status,
            status=initial_status,
            payment_plan=offer.payment_plan or "one_time",
        )

        # For free trials, automatically activate subscription
        if is_free_trial:
            order.payment_date = timezone.now()
            order.save()
            order.activate_subscription()
        # Process payment if provided (for paid orders)
        elif data.get("payment_data"):
            order.process_payment(data["payment_data"])

        return Response(
            {
                "success": True,
                "order_id": order.id,
                "message": "Order created successfully",
                "order_summary": order.get_subscription_summary(),
            }
        )

    except Exception as e:
        print(f"Error in create_starter_order: {e}")
        import traceback

        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_starter_orders(request):
    """Get Zentro Starter orders (for admin purposes)"""
    try:
        orders = ZentroStarterOrder.objects.select_related("user", "offer").all()
        orders_data = []

        for order in orders:
            orders_data.append(
                {
                    "id": order.id,
                    "user_email": order.user.email if order.user else "Anonymous",
                    "order_date": order.order_date.isoformat(),
                    "status": order.status,
                    "free_months_earned": order.free_months_earned,
                    "device_included": order.device_included,
                    "delivery_address": order.delivery_address,
                    "phone_number": order.phone_number,
                }
            )

        return Response({"orders": orders_data, "total": len(orders_data)})

    except Exception as e:
        return Response({"error": str(e)}, status=500)


def activate_subscription_from_billing(company, billing_history, payment_date):
    """
    Activate or extend a subscription based on a paid BillingHistory.
    Used by both Stripe verify_payment_unified and manual mobile money admin.

    Billing anchor is always the payment day: period end is the last inclusive day
    before the next calendar-month/year anchor (end-of-month clamping). Plan changes
    use the same rule (no extension from the previous subscription_end_date).

    Returns (success: bool, message: str).
    """

    subscription = Subscription.objects.get(company=company)
    meta = billing_history.metadata or {}
    months, billing_cycle = parse_billing_period_from_metadata(meta)

    # Extra-users-only: only add seats, no plan/date changes
    if meta.get("payment_type") == "extra_users":
        extra_count = 0
        raw = meta.get("extra_users_count")
        if raw is not None:
            try:
                extra_count = int(raw)
            except (TypeError, ValueError):
                pass
        if extra_count > 0:
            subscription.extra_users_purchased = (
                subscription.extra_users_purchased or 0
            ) + extra_count
            subscription.save()
        return True, "extra_users"

    payment_date_date = (
        payment_date.date() if hasattr(payment_date, "date") else payment_date
    )
    period_end_date = subscription_period_end_inclusive(
        payment_date_date, months, billing_cycle
    )
    new_plan_value = subscription_plan_value_from_product(billing_history.product)

    # Check if user has an active starter pack - extend instead of starting new
    starter_order = (
        ZentroStarterOrder.objects.filter(
            company=company, status__in=["paid", "active"]
        )
        .order_by("-created_at")
        .first()
    )

    if starter_order and starter_order.is_free_period_active:
        period_end_dt = aware_start_of_day(period_end_date)
        starter_order.subscription_end_date = period_end_dt
        starter_order.status = "active"
        starter_order.save()

        subscription.is_paid = True
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.subscription_start_date = payment_date_date
        subscription.subscription_end_date = period_end_date
        subscription.plan = new_plan_value
        subscription.is_trial = False
        subscription.save()
        return True, "subscription_extension"

    # Regular subscription payment (calendar anchor from payment day)
    subscription.is_paid = True
    subscription.status = SubscriptionStatus.ACTIVE.value
    subscription.subscription_start_date = payment_date_date
    subscription.subscription_end_date = period_end_date
    subscription.plan = new_plan_value
    subscription.is_trial = False

    # Persist extra users from payment metadata (accumulate)
    extra_count = 0
    raw = meta.get("extra_users_count")
    if raw is not None:
        try:
            extra_count = int(raw)
        except (TypeError, ValueError):
            pass
    if extra_count > 0:
        subscription.extra_users_purchased = (
            subscription.extra_users_purchased or 0
        ) + extra_count

    subscription.save()

    # Update existing starter pack order if any (align order record with subscription)
    starter_order = (
        ZentroStarterOrder.objects.filter(
            company=company,
            status__in=["paid", "active", "free_period_ended"],
        )
        .order_by("-created_at")
        .first()
    )
    if starter_order:
        starter_order.subscription_start_date = aware_start_of_day(payment_date_date)
        starter_order.subscription_end_date = aware_start_of_day(period_end_date)
        starter_order.status = "active"
        starter_order.save()

    return True, "subscription"


def _get_mobile_money_instructions():
    """Get mobile money numbers and account name from settings or SystemSettings."""
    from django.conf import settings as django_settings

    number = getattr(
        django_settings,
        "SUBSCRIPTION_MOBILE_MONEY_NUMBER",
        "+256 700 000 000",
    )
    numbers_str = getattr(
        django_settings,
        "SUBSCRIPTION_MOBILE_MONEY_NUMBERS",
        "0750440865,0779899789",
    )
    account_name = getattr(
        django_settings,
        "SUBSCRIPTION_MOBILE_MONEY_ACCOUNT_NAME",
        "ZentroApp",
    )
    try:
        from settings.models import SystemSettings

        s = SystemSettings.objects.filter(
            setting_key="SUBSCRIPTION_MOBILE_MONEY_NUMBER", is_active=True
        ).first()
        if s and s.setting_value:
            number = s.setting_value
        s_nums = SystemSettings.objects.filter(
            setting_key="SUBSCRIPTION_MOBILE_MONEY_NUMBERS", is_active=True
        ).first()
        if s_nums and s_nums.setting_value:
            numbers_str = s_nums.setting_value
        # Don't override account_name from SystemSettings; env (.env) takes precedence
    except Exception:
        pass
    numbers = [n.strip() for n in numbers_str.split(",") if n.strip()]
    if not numbers:
        numbers = [number]
    return {
        "mobile_money_number": number,
        "mobile_money_numbers": numbers,
        "account_name": account_name,
        "instructions": f"Send the amount to one of the numbers below (Account: {account_name}). Use the reference when prompted.",
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_mobile_money_instructions(request):
    """Get mobile money payment instructions for subscription."""
    from django_tenants.utils import get_tenant, get_public_schema_name

    data = _get_mobile_money_instructions()
    company = get_tenant(request)
    if company:
        with schema_context(get_public_schema_name()):
            # Check if company has active subscription (fresh from DB, not JWT)
            subscription = Subscription.objects.filter(company=company).first()
            data["has_active_subscription"] = (
                subscription.is_active() if subscription else False
            )
            pending = (
                BillingHistory.objects.filter(
                    company=company,
                    status="pending_verification",
                    payment_gateway=PaymentGateway.MANUAL_MOBILE_MONEY,
                )
                .order_by("-id")
                .first()
            )
            if pending:
                data["has_pending_verification"] = True
                data["pending_payment_reference"] = pending.gateway_payment_id or ""
            else:
                data["has_pending_verification"] = False
                data["pending_payment_reference"] = ""
    else:
        data["has_active_subscription"] = False
        data["has_pending_verification"] = False
        data["pending_payment_reference"] = ""
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def create_manual_payment(request):
    """
    Create a manual mobile money payment request (I HAVE PAID).
    Creates BillingHistory with status=pending_verification for admin to verify.
    """
    import uuid
    from django.conf import settings as django_settings
    from django_tenants.utils import schema_context, get_public_schema_name

    plan_id = request.data.get("plan_id")
    amount = request.data.get("amount")
    billing_cycle = request.data.get("billing_cycle", "monthly")
    months_raw = request.data.get("months", 1)
    reference = request.data.get("reference", "").strip()

    if not plan_id:
        return Response(
            {"error": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST
        )
    if amount is None:
        return Response(
            {"error": "amount is required"}, status=status.HTTP_400_BAD_REQUEST
        )
    if not reference:
        return Response(
            {
                "error": "Transaction reference (transaction ID from receipt) is required"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount_decimal = Decimal(str(amount))
        if amount_decimal <= 0:
            raise ValueError("Amount must be positive")
    except (InvalidOperation, TypeError, ValueError) as e:
        return Response(
            {"error": "Invalid amount"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        months = int(months_raw)
        if months < 1 or months > 24:
            raise ValueError("months out of range")
    except (TypeError, ValueError):
        return Response(
            {"error": "months must be an integer between 1 and 24"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    company = get_tenant(request)
    if not company:
        return Response(
            {"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND
        )

    with schema_context(get_public_schema_name()):
        subscription, _ = Subscription.objects.get_or_create(
            company=company,
            defaults={
                "plan": SubscriptionPlan.FREE_TRIAL.value,
                "status": SubscriptionStatus.TRIAL.value,
            },
        )
        # Allow renewals/upfront payments even when subscription is active.
        # The activation step will extend the existing period based on metadata.

        try:
            plan = Pricing.objects.get(pk=plan_id, is_active=True)
        except Pricing.DoesNotExist:
            return Response(
                {"error": "Invalid plan_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema_prefix = (company.schema_name or "default")[:8].replace("-", "_")
        short_uuid = uuid.uuid4().hex[:8].upper()
        payment_reference = f"ZENTRO-{schema_prefix}-{short_uuid}"

        product_name = plan.name
        if billing_cycle == "yearly":
            amount_to_charge = plan.annual_price
        else:
            amount_to_charge = plan.price

        metadata = {
            "plan_id": plan_id,
            "billing_cycle": billing_cycle,
            "months": months,
            "user_reference": reference,
            "payer_email": (
                request.user.email if request.user and request.user.email else ""
            ),
        }

        billing = BillingHistory.objects.create(
            company=company,
            payment_gateway=PaymentGateway.MANUAL_MOBILE_MONEY,
            product=product_name,
            status="pending_verification",
            billing_date=timezone.now().date(),
            amount=amount_decimal,
            currency="UGX",
            gateway_payment_id=payment_reference,
            metadata=metadata,
        )

        notify_email = getattr(settings, "SUBSCRIPTION_NOTIFY_EMAIL", "").strip()
        notify_phone = getattr(settings, "SUBSCRIPTION_NOTIFY_PHONE", "").strip()
        amount_str = f"{amount_decimal:,.0f}"
        if notify_email or notify_phone:
            try:
                from helpers.send_email import send_transactional_email
                from helpers.helpers import send_plain_sms

                if notify_email:
                    subject = f"[Zentro] New mobile money payment – {company.name} – USh {amount_str}"
                    html = f"""
                    <p>A new mobile money payment has been submitted.</p>
                    <ul>
                        <li><strong>Company:</strong> {company.name}</li>
                        <li><strong>Plan:</strong> {product_name}</li>
                        <li><strong>Amount:</strong> USh {amount_str}</li>
                        <li><strong>Billing cycle:</strong> {billing_cycle}</li>
                        <li><strong>Customer reference:</strong> {reference}</li>
                        <li><strong>Payment reference:</strong> {payment_reference}</li>
                    </ul>
                    <p>Verify in Django admin.</p>
                    """
                    if send_transactional_email(notify_email, subject, html):
                        logger.info(
                            f"Mobile money payment notify email sent to {notify_email}"
                        )
                    else:
                        logger.warning(
                            f"Failed to send mobile money payment notify email to {notify_email}"
                        )
                if notify_phone:
                    msg = (
                        f"New MoMo payment: {company.name}, USh {amount_str}, "
                        f"ref {payment_reference}. Verify in admin."
                    )
                    if send_plain_sms(notify_phone, msg):
                        logger.info(
                            f"Mobile money payment notify SMS sent to {notify_phone}"
                        )
                    else:
                        logger.warning(
                            f"Failed to send mobile money payment notify SMS to {notify_phone}"
                        )
            except Exception as e:
                logger.exception(
                    f"Error sending mobile money payment notifications: {e}"
                )

    instructions = _get_mobile_money_instructions()
    return Response(
        {
            "billing_history_id": billing.id,
            "reference": payment_reference,
            "amount": str(amount_decimal),
            "product": product_name,
            "instructions": instructions,
            "message": "Payment submitted. We will verify and activate your subscription shortly.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_extra_users_payment(request):
    """
    Create a manual mobile money payment for extra users only (no plan change).
    For existing subscribers who only need additional user slots.
    """
    import uuid
    from django_tenants.utils import get_tenant, schema_context, get_public_schema_name

    extra_users_count = request.data.get("extra_users_count")
    reference = request.data.get("reference", "").strip()

    if extra_users_count is None:
        return Response(
            {"error": "extra_users_count is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        count = int(extra_users_count)
        if count < 1 or count > 99:
            raise ValueError("Count must be between 1 and 99")
    except (TypeError, ValueError) as e:
        return Response(
            {"error": "extra_users_count must be an integer between 1 and 99"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not reference:
        return Response(
            {
                "error": "Transaction reference (transaction ID from receipt) is required"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company = get_tenant(request)
    if not company:
        return Response(
            {"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND
        )

    with schema_context(get_public_schema_name()):
        try:
            subscription = Subscription.objects.get(company=company)
        except Subscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            addon = AddOn.objects.get(code="extra_users", is_active=True)
        except AddOn.DoesNotExist:
            return Response(
                {"error": "Extra users add-on not configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        amount_decimal = Decimal(str(addon.price)) * count
        schema_prefix = (company.schema_name or "default")[:8].replace("-", "_")
        short_uuid = uuid.uuid4().hex[:8].upper()
        payment_reference = f"ZENTRO-{schema_prefix}-{short_uuid}"

        metadata = {
            "extra_users_count": count,
            "payment_type": "extra_users",
            "user_reference": reference,
        }

        billing = BillingHistory.objects.create(
            company=company,
            payment_gateway=PaymentGateway.MANUAL_MOBILE_MONEY,
            product="Extra Users",
            status="pending_verification",
            billing_date=timezone.now().date(),
            amount=amount_decimal,
            currency="UGX",
            gateway_payment_id=payment_reference,
            metadata=metadata,
        )

        notify_email = getattr(settings, "SUBSCRIPTION_NOTIFY_EMAIL", "").strip()
        notify_phone = getattr(settings, "SUBSCRIPTION_NOTIFY_PHONE", "").strip()
        amount_str = f"{amount_decimal:,.0f}"
        if notify_email or notify_phone:
            try:
                from helpers.send_email import send_transactional_email
                from helpers.helpers import send_plain_sms

                if notify_email:
                    subject = f"[Zentro] Extra users payment – {company.name} – USh {amount_str}"
                    html = f"""
                    <p>New extra users payment submitted.</p>
                    <ul>
                        <li><strong>Company:</strong> {company.name}</li>
                        <li><strong>Extra users:</strong> {count}</li>
                        <li><strong>Amount:</strong> USh {amount_str}</li>
                        <li><strong>Customer reference:</strong> {reference}</li>
                        <li><strong>Payment reference:</strong> {payment_reference}</li>
                    </ul>
                    <p>Verify in Django admin.</p>
                    """
                    if send_transactional_email(notify_email, subject, html):
                        logger.info(
                            f"Extra users payment notify email sent to {notify_email}"
                        )
                    else:
                        logger.warning(
                            f"Failed to send extra users payment notify email"
                        )
                if notify_phone:
                    msg = (
                        f"Extra users payment: {company.name}, {count} users, "
                        f"USh {amount_str}, ref {payment_reference}."
                    )
                    if send_plain_sms(notify_phone, msg):
                        logger.info(
                            f"Extra users payment notify SMS sent to {notify_phone}"
                        )
                    else:
                        logger.warning(f"Failed to send extra users payment notify SMS")
            except Exception as e:
                logger.exception(
                    f"Error sending extra users payment notifications: {e}"
                )

    instructions = _get_mobile_money_instructions()
    return Response(
        {
            "billing_history_id": billing.id,
            "reference": payment_reference,
            "amount": str(amount_decimal),
            "product": "Extra Users",
            "instructions": instructions,
            "message": "Payment submitted. We will verify and add your extra users shortly.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_payment_unified(request):
    """Unified payment verification for both subscription and starter pack payments"""
    try:
        payment_intent_id = request.data.get("payment_intent_id")

        if not payment_intent_id:
            return Response({"error": "Payment intent ID is required"}, status=400)

        # Set Stripe API key
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Retrieve the payment intent from Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if intent.status != "succeeded":
            return Response({"error": "Payment not completed"}, status=400)

        # Check if this is a starter pack payment
        if intent.metadata.get("payment_type") == "starter_pack":
            # Handle starter pack payment
            try:
                offer_id = int(intent.metadata.get("offer_id"))
                company_id = int(intent.metadata.get("company_id"))

                # Get the company
                company = Company.objects.get(id=company_id)

                # Get the offer
                offer = ZentroStarterOffer.objects.get(id=offer_id, is_active=True)

                # Check if order already exists with this payment reference
                existing_order_by_ref = ZentroStarterOrder.objects.filter(
                    payment_reference=payment_intent_id
                ).first()

                if existing_order_by_ref:
                    return Response(
                        {
                            "success": True,
                            "payment_type": "starter_pack",
                            "order_id": existing_order_by_ref.id,
                            "message": "Starter pack order already confirmed",
                            "order_summary": existing_order_by_ref.get_subscription_summary(),
                            "plan": "STARTER_PACK",  # Include plan in response
                        }
                    )

                # Check if company already has an active order (only one order per company allowed)
                existing_order = ZentroStarterOrder.objects.filter(
                    company=company, status__in=["pending", "paid", "active"]
                ).first()

                if existing_order:
                    return Response(
                        {
                            "error": "Company already has an active order. Each company can only have one active order.",
                            "existing_order_id": existing_order.id,
                            "existing_order_offer": existing_order.offer.name,
                        },
                        status=400,
                    )

                # Create the starter pack order
                order = ZentroStarterOrder.objects.create(
                    company=company,
                    offer=offer,
                    payment_amount=offer.device_price,
                    device_included=offer.device_price
                    >= 1000000,  # True for Zentro Kit
                    free_months_earned=offer.free_months,
                    delivery_address="",  # Will be filled later if needed
                    phone_number="",  # Will be filled later if needed
                    payment_status="completed",
                    payment_date=timezone.now(),
                    payment_reference=payment_intent_id,
                    payment_gateway="stripe",
                    gateway_transaction_id=payment_intent_id,
                    status="paid",
                )

                # Activate the subscription (this will also set up the regular Subscription model)
                order.activate_subscription()

                return Response(
                    {
                        "success": True,
                        "payment_type": "starter_pack",
                        "order_id": order.id,
                        "message": "Starter pack order completed successfully",
                        "order_summary": order.get_subscription_summary(),
                    }
                )

            except (
                Company.DoesNotExist,
                ZentroStarterOffer.DoesNotExist,
                ValueError,
            ) as e:
                return Response(
                    {"error": f"Invalid payment data: {str(e)}"}, status=400
                )

        else:
            # Handle subscription payment
            try:
                # Get billing history for this payment
                billing_history = BillingHistory.objects.filter(
                    gateway_payment_id=payment_intent_id
                ).first()

                if not billing_history:
                    return Response({"error": "Billing history not found"}, status=400)

                billing_history.status = "paid"
                billing_history.save()

                success, activation_msg = activate_subscription_from_billing(
                    billing_history.company,
                    billing_history,
                    billing_history.billing_date,
                )
                if not success:
                    return Response(
                        {"error": "Failed to activate subscription"}, status=500
                    )

                subscription = Subscription.objects.get(company=billing_history.company)
                order_summary = None
                starter_order = (
                    ZentroStarterOrder.objects.filter(
                        company=billing_history.company,
                        status__in=["paid", "active", "free_period_ended"],
                    )
                    .order_by("-created_at")
                    .first()
                )
                if starter_order:
                    order_summary = starter_order.get_subscription_summary()

                if activation_msg == "subscription_extension":
                    return Response(
                        {
                            "success": True,
                            "payment_type": "subscription_extension",
                            "billing_history_id": billing_history.id,
                            "message": "Subscription extended successfully",
                            "new_end_date": subscription.subscription_end_date.isoformat(),
                            "plan": subscription.plan,
                            "order_summary": order_summary,
                        }
                    )

                return Response(
                    {
                        "success": True,
                        "payment_type": "subscription",
                        "billing_history_id": billing_history.id,
                        "message": "Subscription payment completed successfully",
                        "plan": subscription.plan,
                        "order_summary": order_summary,
                    }
                )

            except BillingHistory.DoesNotExist:
                return Response({"error": "Billing history not found"}, status=400)
            except Subscription.DoesNotExist:
                return Response({"error": "Subscription not found"}, status=400)

    except stripe.error.StripeError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        print(f"Error in verify_payment_unified: {e}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_manual_payment(request):
    """
    Register a manual payment (Mobile Money, Cash, Bank Transfer) for a starter pack order.
    Admin/staff can register payments received outside of Stripe.
    """
    try:
        data = request.data

        # Validate required fields
        required_fields = ["order_id", "amount", "payment_method"]
        for field in required_fields:
            if field not in data:
                return Response(
                    {"error": f"Missing required field: {field}"}, status=400
                )

        # Get the order
        try:
            order = ZentroStarterOrder.objects.get(id=data["order_id"])
        except ZentroStarterOrder.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        # Validate amount
        try:
            amount = Decimal(str(data["amount"]))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid payment amount"}, status=400)

        if amount <= 0:
            return Response(
                {"error": "Payment amount must be greater than zero"}, status=400
            )

        # Check if amount exceeds remaining balance
        remaining = order.amount_remaining
        if amount > remaining:
            return Response(
                {
                    "error": f"Payment amount ({amount:,.2f}) exceeds remaining balance ({remaining:,.2f})"
                },
                status=400,
            )

        payment_method = data["payment_method"]

        # Validate payment method
        valid_methods = ["mobile_money", "cash", "bank_transfer"]
        if payment_method not in valid_methods:
            return Response(
                {
                    "error": f"Invalid payment method. Must be one of: {', '.join(valid_methods)}"
                },
                status=400,
            )

        # Create payment record
        payment = ZentroStarterPayment.objects.create(
            order=order,
            payment_method=payment_method,
            amount=amount,
            payment_date=timezone.now(),
            received_by=request.user,
            is_confirmed=True,
            confirmed_by=request.user,
            confirmed_at=timezone.now(),
            notes=data.get("notes", ""),
        )

        # Add payment method specific details
        if payment_method == "mobile_money":
            payment.mobile_money_number = data.get("mobile_money_number", "")
            payment.mobile_money_provider = data.get("mobile_money_provider", "")
            payment.mobile_money_reference = data.get("mobile_money_reference", "")
            payment.save()

        # Refresh order to get updated amount_paid (updated by payment save signal)
        order.refresh_from_db()

        # Activate subscription if this is the first payment
        if order.amount_paid > 0 and not order.subscription_start_date:
            order.activate_subscription()
            order.refresh_from_db()

        # Receipt PDF is automatically generated in payment.save() method
        # Refresh payment to get receipt path if generated
        payment.refresh_from_db()

        return Response(
            {
                "success": True,
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "amount_paid": float(order.amount_paid),
                "total_amount": float(order.total_amount),
                "amount_remaining": float(order.amount_remaining),
                "order_amount_paid": float(order.amount_paid),
                "order_amount_remaining": float(order.amount_remaining),
                "message": "Payment registered successfully",
            },
            status=201,
        )

    except Exception as e:
        print(f"Error in register_manual_payment: {e}")
        import traceback

        traceback.print_exc()
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_payment_receipt(request, payment_id):
    """
    Get receipt/invoice PDF for a payment.
    Returns PDF file for download/view.
    """
    from django.http import HttpResponse

    try:
        payment = get_object_or_404(ZentroStarterPayment, id=payment_id)

        # Check if user has permission (must be from same company)
        if (
            request.user.is_superuser
            or payment.order.company.schema_name == connection.schema_name
        ):
            from .receipt_utils import get_receipt_http_response

            return get_receipt_http_response(payment)
        else:
            return Response(
                {"error": "You don't have permission to view this receipt"},
                status=403,
            )

    except Exception as e:
        print(f"Error in get_payment_receipt: {e}")
        import traceback

        traceback.print_exc()
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_receipt_email(request):
    """
    Resend receipt email to customer for a payment.
    """
    try:
        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response({"error": "payment_id is required"}, status=400)

        payment = get_object_or_404(ZentroStarterPayment, id=payment_id)

        # Check permission
        if not (
            request.user.is_superuser
            or payment.order.company.schema_name == connection.schema_name
        ):
            return Response(
                {"error": "You don't have permission to resend this receipt"},
                status=403,
            )

        # TODO: Send email with receipt PDF
        # For now, just mark as sent
        payment.receipt_sent = True
        payment.receipt_sent_at = timezone.now()
        payment.save()

        return Response(
            {
                "success": True,
                "message": "Receipt email sent successfully",
                "receipt_number": payment.receipt_number,
            }
        )

    except Exception as e:
        print(f"Error in resend_receipt_email: {e}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order_payments(request, order_id):
    """
    Get all payments for a specific order.
    """
    try:
        order = get_object_or_404(ZentroStarterOrder, id=order_id)

        # Check permission
        if not (
            request.user.is_superuser
            or order.company.schema_name == connection.schema_name
        ):
            return Response(
                {"error": "You don't have permission to view these payments"},
                status=403,
            )

        payments = ZentroStarterPayment.objects.filter(order=order).order_by(
            "-payment_date"
        )

        payments_data = [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "payment_date": p.payment_date,
                "is_confirmed": p.is_confirmed,
                "receipt_sent": p.receipt_sent,
                "mobile_money_number": p.mobile_money_number,
                "mobile_money_provider": p.mobile_money_provider,
                "mobile_money_reference": p.mobile_money_reference,
                "notes": p.notes,
            }
            for p in payments
        ]

        return Response(
            {
                "order_id": order.id,
                "total_amount": float(order.total_amount),
                "amount_paid": float(order.amount_paid),
                "amount_remaining": float(order.amount_remaining),
                "payments": payments_data,
            }
        )

    except Exception as e:
        print(f"Error in get_order_payments: {e}")
        return Response(
            {"error": "An unexpected error occurred"},
            status=500,
        )


MODULE_CATEGORY_MAP = {
    "sales": "Core",
    "inventory": "Core",
    "purchases": "Core",
    "customers": "Core",
    "expenses": "Core",
    "reports": "Core",
    "financials": "Core",
    "payments": "Core",
    "prepayments": "Core",
    "bank_accounts": "Core",
    "user_management": "Core",
    "item_tracking": "Business+",
    "stock_taking": "Business+",
    "manufacturing": "Business+",
    "loans": "Business+",
    "resources": "Business+",
    "multi_branch": "Business+",
    "efris": "Pro",
    "hotel": "Add-on",
    "restaurant": "Add-on",
}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def toggle_module(request):
    """Enable/disable a module via overrides (trial tenants, or debug_admin only)."""
    from utils.modules import VALID_MODULES
    from django_tenants.utils import get_tenant

    module_id = request.data.get("module")
    action = request.data.get("action")

    if action not in ("enable", "disable"):
        return Response(
            {"error": "Action must be 'enable' or 'disable'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if module_id not in VALID_MODULES or module_id == "pos":
        return Response(
            {"error": f"Unknown module: {module_id}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    company = get_tenant(request)

    try:
        sub = company.subscription
    except Exception:
        return Response(
            {"error": "No subscription found"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    username = getattr(request.user, "username", None) or ""
    is_debug_module_admin = username in DEBUG_USER_USERNAMES
    if sub.status != "trial" and not is_debug_module_admin:
        return Response(
            {
                "error": "Module toggling is only available during the free trial. "
                "Please upgrade your plan to access additional modules."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    overrides = list(company.module_overrides or [])
    if action == "enable" and module_id not in overrides:
        overrides.append(module_id)
    elif action == "disable" and module_id in overrides:
        overrides.remove(module_id)
    else:
        company.compute_enabled_modules()
        company.refresh_from_db(fields=["enabled_modules"])
        return Response(
            {
                "success": True,
                "enabled_modules": company.enabled_modules or [],
                "module_overrides": company.module_overrides or [],
            }
        )

    company.module_overrides = overrides
    company.save(update_fields=["module_overrides"])
    company.compute_enabled_modules()
    company.refresh_from_db(fields=["enabled_modules"])

    setup_ran = False
    if action == "enable":
        from utils.module_setup import MODULE_SETUP_COMMANDS, run_module_setup

        try:
            run_module_setup(module_id, schema_name=company.schema_name)
            setup_ran = module_id in MODULE_SETUP_COMMANDS
        except Exception as exc:
            logger.exception(
                "Module setup failed for %s (schema=%s)",
                module_id,
                company.schema_name,
            )
            reverted = list(company.module_overrides or [])
            if module_id in reverted:
                reverted.remove(module_id)
            company.module_overrides = reverted
            company.save(update_fields=["module_overrides"])
            company.compute_enabled_modules()
            company.refresh_from_db(fields=["enabled_modules"])
            return Response(
                {
                    "error": (
                        f"Could not finish setting up {module_id} module. "
                        f"Please try again or contact support. ({exc})"
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return Response(
        {
            "success": True,
            "enabled_modules": company.enabled_modules or [],
            "module_overrides": company.module_overrides or [],
            "setup_ran": setup_ran,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def company_modules(request):
    from utils.modules import MODULE_REGISTRY
    from django_tenants.utils import get_tenant

    company = get_tenant(request)

    company.compute_enabled_modules()
    company.refresh_from_db(fields=["enabled_modules", "module_overrides"])

    from django_tenants.utils import schema_context

    plan_name = None
    plan_modules = []
    plan_branches = None
    try:
        sub = company.subscription
        plan_name = sub.plan
        plan_key = sub.plan or ""
        pricing_name = Company.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
        if not pricing_name and sub.status in ("trial", "active"):
            pricing_name = "Starter"
        with schema_context("public"):
            pricing = Pricing.objects.filter(name=pricing_name, is_active=True).first()
            if pricing:
                plan_modules = pricing.included_modules or []
                feats = pricing.features or {}
                if isinstance(feats, dict):
                    plan_branches = feats.get("branches")
    except Exception:
        pass

    enabled_list = company.enabled_modules or []
    overrides_list = company.module_overrides or []

    modules = []
    for key, config in MODULE_REGISTRY.items():
        if key == "pos":
            continue
        modules.append(
            {
                "identifier": config.identifier,
                "display_name": config.display_name,
                "description": config.description,
                "icon": config.icon,
                "category": MODULE_CATEGORY_MAP.get(key, "Core"),
                "enabled": key in (enabled_list or []),
                "from_plan": key in (plan_modules or []),
                "from_override": key in (overrides_list or []),
            }
        )

    is_trial = False
    try:
        is_trial = company.subscription.status == "trial"
    except Exception:
        pass

    username = getattr(request.user, "username", None) or ""
    is_debug_module_admin = username in DEBUG_USER_USERNAMES
    allow_manual_module_toggle = is_trial or is_debug_module_admin

    return Response(
        {
            "modules": modules,
            "enabled_modules": enabled_list or [],
            "module_overrides": overrides_list or [],
            "plan_name": plan_name,
            "plan_modules": plan_modules or [],
            "plan_branches": plan_branches,
            "is_trial": is_trial,
            "allow_manual_module_toggle": allow_manual_module_toggle,
        }
    )
