from django.shortcuts import render

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


from company.forms import CompanyOnBoardingForm, CompanyForm
from company.models import BusinessObjective, BusinessCategory, Pricing
from home.serializers import (
    PricingSerializer,
    BusinessObjectiveSerializer,
    BusinessCategorySerializer,
)


@api_view(["GET"])
def landing_page_api(request):
    try:
        pricing_info = Pricing.objects.order_by("order")
        serializer = PricingSerializer(pricing_info, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def onboarding_api(request):
    if request.method == "GET":
        # Get all reference data
        business_objectives = BusinessObjective.objects.all()
        business_categories = BusinessCategory.objects.all()

        return Response(
            {
                "business_objectives": BusinessObjectiveSerializer(
                    business_objectives, many=True
                ).data,
                "business_categories": BusinessCategorySerializer(
                    business_categories, many=True
                ).data,
            }
        )


def onboarding(request):
    form = CompanyOnBoardingForm()
    company_form = CompanyForm()
    business_objectives = BusinessObjective.objects.all()
    business_categories = BusinessCategory.objects.all()
    context = {
        "form": form,
        "business_objectives": business_objectives,
        "business_categories": business_categories,
        "company_form": company_form,
    }
    return render(request, "home/onboarding.html", context)


@api_view(["GET"])
def get_onboarding_data(request):
    if request.method == "GET":
        # Get all reference data
        business_objectives = BusinessObjective.objects.all()
        business_categories = BusinessCategory.objects.all()

        return Response(
            {
                "business_objectives": BusinessObjectiveSerializer(
                    business_objectives, many=True
                ).data,
                "business_categories": BusinessCategorySerializer(
                    business_categories, many=True
                ).data,
            }
        )
    # data = {
    #     "business_objectives": [
    #         {
    #             "id": 1,
    #             "created_at": "2024-01-01T03:00:00+03:00",
    #             "updated_at": "2024-01-01T03:00:00+03:00",
    #             "system_id": "660e8400-e29b-41d4-a716-446655440000",
    #             "description": "Start a New Business",
    #             "icon_path": "M3 3h18v18H3zM12 8v8m-4-4h8",
    #             "icon_type": "outline",
    #             "is_active": True,
    #         },
    #         # ... other objectives
    #     ],
    #     "business_categories": [
    #         {
    #             "id": 1,
    #             "created_at": "2024-01-01T03:00:00+03:00",
    #             "updated_at": "2024-01-01T03:00:00+03:00",
    #             "system_id": "550e8400-e29b-41d4-a716-446655440000",
    #             "name": "Others",
    #             "icon_path": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
    #             "icon_type": "outline",
    #             "is_active": True,
    #         },
    #         # ... other categories
    #     ],
    # }
    # return Response(data, status=status.HTTP_200_OK)
