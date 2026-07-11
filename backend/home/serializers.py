from rest_framework.serializers import ModelSerializer, ValidationError

from company.models import (
    Pricing,
    CompanyOnBoarding,
    Company,
    BusinessObjective,
    BusinessCategory,
)
from utils.modules import validate_module_list


class PricingSerializer(ModelSerializer):

    class Meta:
        model = Pricing
        fields = "__all__"


class OnBoardingSerializer(ModelSerializer):
    class Meta:
        model = CompanyOnBoarding
        fields = "__all__"


class BusinessObjectiveSerializer(ModelSerializer):
    class Meta:
        model = BusinessObjective
        fields = "__all__"


class BusinessCategorySerializer(ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = "__all__"


class CompanySerializer(ModelSerializer):
    class Meta:
        model = Company
        fields = ["name", "address", "email", "phone", "enabled_modules"]
        read_only_fields = []

    def validate_enabled_modules(self, value):
        """
        Validate that all modules in the list are valid and dependencies are met
        Ensures POS module is always included
        """
        if not isinstance(value, list):
            raise ValidationError("enabled_modules must be a list")

        # Ensure POS is always included
        if "pos" not in value:
            value = ["pos"] + [m for m in value if m != "pos"]

        # Validate modules using the module registry
        is_valid, error_message = validate_module_list(value)
        if not is_valid:
            raise ValidationError(error_message)

        return value

    def validate(self, attrs):
        """
        Additional validation for module updates
        Prevents disabling POS module and validates dependencies
        """
        # If updating enabled_modules
        if "enabled_modules" in attrs:
            new_modules = attrs["enabled_modules"]

            # Prevent disabling POS module
            if "pos" not in new_modules:
                raise ValidationError(
                    {
                        "enabled_modules": "POS module cannot be disabled. It is the base module required for all companies."
                    }
                )

            # If updating an existing instance, check for module removals
            if self.instance:
                current_modules = set(self.instance.enabled_modules or [])
                new_modules_set = set(new_modules)

                # Check if any modules are being removed
                removed_modules = current_modules - new_modules_set
                if removed_modules:
                    # Prevent removing POS
                    if "pos" in removed_modules:
                        raise ValidationError(
                            {
                                "enabled_modules": "POS module cannot be disabled. It is the base module required for all companies."
                            }
                        )

                    # Import here to avoid circular dependency
                    from utils.modules import get_modules_requiring_module

                    # Check if any other enabled modules depend on the removed ones
                    for removed_module in removed_modules:
                        dependent_modules = get_modules_requiring_module(removed_module)
                        still_enabled = [
                            mod for mod in dependent_modules if mod in new_modules_set
                        ]
                        if still_enabled:
                            raise ValidationError(
                                {
                                    "enabled_modules": f"Cannot disable module '{removed_module}' because the following enabled modules depend on it: {', '.join(still_enabled)}"
                                }
                            )

        return super().validate(attrs)


class CompanyOnBoardingSerializer(ModelSerializer):
    class Meta:
        model = CompanyOnBoarding
        fields = ["company_size", "business_objective", "business_category"]
