from rest_framework import serializers
from .models import PaymentMethod, BillingHistory, Subscription, Pricing, AddOn
from django.utils import timezone
from company.subscription_grace import period_end_date, payment_due_date


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "payment_gateway",
            "method_type",
            "holder_name",
            "last_four_digits",
            "expiry_date",
            "is_primary",
            "is_active",
        ]
        read_only_fields = ["gateway_payment_method_id", "gateway_fingerprint"]

    def create(self, validated_data):
        # Add the company from the request user
        validated_data["company"] = self.context["request"].user.company
        return super().create(validated_data)


class BillingHistorySerializer(serializers.ModelSerializer):
    payment_method = PaymentMethodSerializer(read_only=True)

    class Meta:
        model = BillingHistory
        fields = [
            "id",
            "reference_number",
            "product",
            "status",
            "billing_date",
            "amount",
            "currency",
            "payment_method",
            "gateway_payment_id",
            "gateway_invoice_id",
            "metadata",
        ]
        read_only_fields = [
            "reference_number",
            "gateway_payment_id",
            "gateway_invoice_id",
        ]

    def create(self, validated_data):
        # Add the company from the request user
        validated_data["company"] = self.context["request"].user.company
        return super().create(validated_data)


class SubscriptionSerializer(serializers.ModelSerializer):
    is_trial_active = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    in_grace_period = serializers.SerializerMethodField()
    grace_days_remaining = serializers.SerializerMethodField()
    access_lock_date = serializers.SerializerMethodField()
    payment_due_date = serializers.SerializerMethodField()
    period_end_date = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "subscription_start_date",
            "subscription_end_date",
            "trial_period_end_date",
            "is_paid",
            "payment_gateway",
            "billing_cycle",
            "is_trial_active",
            "is_active",
            "days_remaining",
            "in_grace_period",
            "grace_days_remaining",
            "access_lock_date",
            "payment_due_date",
            "period_end_date",
        ]
        read_only_fields = [
            "subscription_start_date",
            "subscription_end_date",
            "trial_period_end_date",
            "is_paid",
        ]

    def get_days_remaining(self, obj):
        """Days until period end (last inclusive paid/trial day); 0 on that day or after."""
        today = timezone.now().date()
        end = period_end_date(obj)
        if end is None:
            return 0
        return max(0, (end - today).days)

    def get_in_grace_period(self, obj):
        return obj.is_in_grace_period()

    def get_grace_days_remaining(self, obj):
        if not obj.is_in_grace_period():
            return None
        lock = obj.access_lock_date()
        today = timezone.now().date()
        if lock is None:
            return None
        return max(0, (lock - today).days)

    def get_access_lock_date(self, obj):
        lock = obj.access_lock_date()
        return lock.isoformat() if lock else None

    def get_payment_due_date(self, obj):
        due = payment_due_date(obj)
        return due.isoformat() if due else None

    def get_period_end_date(self, obj):
        end = period_end_date(obj)
        return end.isoformat() if end else None

    def update(self, instance, validated_data):
        action = self.context.get("action")

        if action == "activate":
            gateway_subscription_id = self.context.get("gateway_subscription_id")
            if not gateway_subscription_id:
                raise serializers.ValidationError("Subscription ID is required")

            if not instance.activate_paid_plan(gateway_subscription_id):
                raise serializers.ValidationError("Failed to activate subscription")

        elif action == "cancel":
            instance.cancel()

        elif action == "renew":
            instance.renew()

        return super().update(instance, validated_data)


class PricingSerializer(serializers.ModelSerializer):
    """
    Serializer for Pricing plans
    """

    monthly_price_display = serializers.CharField(read_only=True)
    annual_price_display = serializers.CharField(read_only=True)
    tagline = serializers.SerializerMethodField()
    best_for = serializers.SerializerMethodField()
    users_included = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()

    class Meta:
        model = Pricing
        fields = [
            "id",
            "name",
            "price",
            "annual_price",
            "trial_period",
            "max_products",
            "features",
            "order",
            "is_popular",
            "is_active",
            "monthly_price_display",
            "annual_price_display",
            "tagline",
            "best_for",
            "users_included",
            "branches",
        ]
        read_only_fields = [
            "monthly_price_display",
            "annual_price_display",
            "tagline",
            "best_for",
            "users_included",
            "branches",
        ]

    def get_tagline(self, obj):
        return (obj.features or {}).get("tagline", "")

    def get_best_for(self, obj):
        return (obj.features or {}).get("best_for", "")

    def get_users_included(self, obj):
        return (obj.features or {}).get("users_included")

    def get_branches(self, obj):
        return (obj.features or {}).get("branches", "")

    def to_representation(self, instance):
        """Custom representation to ensure display fields are included"""
        data = super().to_representation(instance)
        data["monthly_price_display"] = instance.monthly_price_display
        data["annual_price_display"] = instance.annual_price_display
        return data


class AddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddOn
        fields = ["id", "code", "name", "price", "description", "is_per_unit", "order"]


class CompanyOverviewSerializer(serializers.Serializer):
    """
    Serializer for company overview data
    """

    company = serializers.DictField()
    subscription = SubscriptionSerializer()
    stats = serializers.DictField()
    payment_methods = PaymentMethodSerializer(many=True)
    recent_billing = BillingHistorySerializer(many=True)
