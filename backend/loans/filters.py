from django_filters import rest_framework as filters
from .models import Loan, LoanRepayment


class LoanFilter(filters.FilterSet):
    """FilterSet for Loan model"""

    loan_type = filters.CharFilter(field_name="loan_type", lookup_expr="exact")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    posted = filters.BooleanFilter(field_name="posted", lookup_expr="exact")
    repayment_account = filters.CharFilter(
        field_name="repayment_account", lookup_expr="exact"
    )
    disbursement_date = filters.DateFilter(
        field_name="disbursement_date", lookup_expr="exact"
    )
    disbursement_date_from = filters.DateFilter(
        field_name="disbursement_date", lookup_expr="gte"
    )
    disbursement_date_to = filters.DateFilter(
        field_name="disbursement_date", lookup_expr="lte"
    )
    lender_name = filters.CharFilter(
        field_name="lender_name", lookup_expr="icontains"
    )

    class Meta:
        model = Loan
        fields = [
            "loan_type",
            "status",
            "posted",
            "repayment_account",
            "disbursement_date",
            "disbursement_date_from",
            "disbursement_date_to",
            "lender_name",
        ]


class LoanRepaymentFilter(filters.FilterSet):
    """FilterSet for LoanRepayment model"""

    loan = filters.NumberFilter(field_name="loan", lookup_expr="exact")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    posted = filters.BooleanFilter(field_name="posted", lookup_expr="exact")
    payment_method = filters.CharFilter(
        field_name="payment_method", lookup_expr="exact"
    )
    payment_date = filters.DateFilter(field_name="payment_date", lookup_expr="exact")
    payment_date_from = filters.DateFilter(
        field_name="payment_date", lookup_expr="gte"
    )
    payment_date_to = filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = LoanRepayment
        fields = [
            "loan",
            "status",
            "posted",
            "payment_method",
            "payment_date",
            "payment_date_from",
            "payment_date_to",
        ]

