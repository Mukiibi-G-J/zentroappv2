from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db import transaction
import uuid
from datetime import datetime
import logging

from authentication.models import CustomUser
from purchases.models import Vendor, VendorLedger
from sales.models import CustomerLedgerEntry
from .enums import ApplicationStatus
from .models import PaymentJournal
from .serializers import PaymentJournalSerializer, PaymentJournalListSerializer
from .journal_application import (
    JOURNAL_SOURCE_GENERAL,
    JOURNAL_SOURCE_PAYMENT,
    ApplyingDocumentNotFound,
    applying_document_no,
    applying_party_no,
    clear_applies_to_stamps_for_document,
    clear_application,
    is_applying_document_posted,
    ledger_entry_allows_applies_to_stamp,
    resolve_applying_document,
    set_customer_application,
    set_vendor_application,
)

logger = logging.getLogger(__name__)


def _payment_document_applies_to_id(payment_journal: PaymentJournal) -> str:
    """BC Applies-to ID on ledger rows = payment document no. while applying."""
    return applying_document_no(payment_journal)


def _journal_source_from_request(request) -> str:
    source = (request.data.get("journal_source") or JOURNAL_SOURCE_PAYMENT).strip().lower()
    if source in (JOURNAL_SOURCE_PAYMENT, JOURNAL_SOURCE_GENERAL):
        return source
    return JOURNAL_SOURCE_PAYMENT


def _load_applying_document(request):
    system_id = request.data.get("system_id")
    if not system_id:
        return None, Response(
            {"error": "system_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    journal_source = _journal_source_from_request(request)
    try:
        return resolve_applying_document(system_id, journal_source), None
    except ApplyingDocumentNotFound as exc:
        return None, Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


def _set_ledger_entry_applies_to_id(entry, applies_to_id: str) -> None:
    entry.applies_to_id = applies_to_id
    entry.save(update_fields=["applies_to_id", "updated_at"])


def _clear_ledger_entry_applies_to_id_if_matches(entry, applies_to_id: str) -> None:
    if (entry.applies_to_id or "").strip() == applies_to_id:
        entry.applies_to_id = ""
        entry.save(update_fields=["applies_to_id", "updated_at"])


# Filters
class PaymentJournalFilter(filters.FilterSet):
    posting_date_from = filters.DateFilter(field_name="posting_date", lookup_expr="gte")
    posting_date_to = filters.DateFilter(field_name="posting_date", lookup_expr="lte")
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = PaymentJournal
        fields = {
            "document_type": ["exact"],
            "account_type": ["exact"],
            "bal_account_type": ["exact"],
            "status": ["exact"],
            "application_status": ["exact"],
            "document_no": ["exact", "icontains"],
            "external_document_no": ["exact", "icontains"],
            "applies_to_doc_type": ["exact", "icontains"],
        }


# ViewSets
class PaymentJournalViewSet(viewsets.ModelViewSet):
    queryset = PaymentJournal.objects.all()
    serializer_class = PaymentJournalSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_class = PaymentJournalFilter
    search_fields = [
        "document_no",
        "external_document_no",
        "description",
    ]
    ordering_fields = [
        "posting_date",
        "document_no",
        "amount",
        "created_at",
    ]
    ordering = ["-posting_date", "-document_no"]

    def perform_create(self, serializer):

        external_document_no = serializer.validated_data.get("external_document_no")
        # make this date with minutes and seconds
        date = datetime.now().strftime("%Y%m%d%H%M%S")
        serializer.save(
            external_document_no=f"{serializer.validated_data.get('description')}-{date}"
        )

    def perform_update(self, serializer):
        description = serializer.validated_data.get("description")
        date = datetime.now().strftime("%Y%m%d%H%M%S")
        serializer.save(external_document_no=f"{description}-{date}")

    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == "list":
            return PaymentJournalListSerializer
        return PaymentJournalSerializer

    def get_queryset(self):
        """Optimize queryset with select_related for better performance"""
        queryset = super().get_queryset()
        if self.action == "list":
            return queryset.select_related(
                "account_content_type",
                "bal_account_content_type",
                "payment_method",
            )
        return queryset.select_related(
            "account_content_type",
            "bal_account_content_type",
            "payment_method",
        )

    @action(detail=False, methods=["get"])
    def content_types(self, request):
        """Get content types for payment journal accounts"""
        # Get content types for models that can be used as accounts
        content_types = ContentType.objects.filter(
            model__in=["vendor", "customer", "g_laccount"]
        ).values("id", "app_label", "model")

        # Add a computed name field for each content type
        result = []
        for ct in content_types:
            result.append(
                {
                    "id": ct["id"],
                    "app_label": ct["app_label"],
                    "model": ct["model"],
                    "name": f"{ct['app_label']}.{ct['model']}",
                }
            )

        return Response(result)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get summary statistics for payment journal entries"""
        queryset = self.filter_queryset(self.get_queryset())

        # Calculate totals
        total_amount = queryset.aggregate(total=Sum("amount"))["total"] or 0
        total_payments = (
            queryset.filter(document_type="PAYMENT").aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )
        total_refunds = (
            queryset.filter(document_type="REFUND").aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )
        applied_count = queryset.filter(application_status="APPLIED").count()
        unapplied_count = queryset.filter(application_status="UNAPPLIED").count()

        # Count by account type
        customer_count = queryset.filter(account_type="CUSTOMER").count()
        vendor_count = queryset.filter(account_type="VENDOR").count()
        gl_count = queryset.filter(account_type="GL").count()

        return Response(
            {
                "total_entries": queryset.count(),
                "total_amount": float(total_amount),
                "total_payments": float(total_payments),
                "total_refunds": float(total_refunds),
                "applied_count": applied_count,
                "unapplied_count": unapplied_count,
                "by_account_type": {
                    "customer": customer_count,
                    "vendor": vendor_count,
                    "gl": gl_count,
                },
            }
        )

    @action(detail=False, methods=["get"])
    def by_account_type(self, request):
        """Get payment journal entries grouped by account type"""
        account_type = request.query_params.get("account_type")
        if not account_type:
            return Response(
                {"error": "account_type parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.filter_queryset(self.get_queryset()).filter(
            account_type=account_type
        )
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "account_type": account_type,
                "count": queryset.count(),
                "total_amount": float(
                    queryset.aggregate(total=Sum("amount"))["total"] or 0
                ),
                "entries": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def unapplied(self, request):
        """Get unapplied payment journal entries"""
        queryset = self.filter_queryset(self.get_queryset()).filter(
            application_status="UNAPPLIED"
        )
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "count": queryset.count(),
                "total_amount": float(
                    queryset.aggregate(total=Sum("amount"))["total"] or 0
                ),
                "entries": serializer.data,
            }
        )

    @action(detail=False, methods=["post"], url_path="apply-vendor-entry")
    def apply_vendor_entry(self, request):
        """Apply payment journal header to an open vendor ledger entry (BC Apply Vendor Entries)."""
        vendor_ledger_id = request.data.get("vendor_ledger_id")

        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if not vendor_ledger_id:
            return Response(
                {"error": "system_id and vendor_ledger_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot apply entries on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            vendor_ledger = VendorLedger.objects.select_related("vendor").get(
                pk=vendor_ledger_id,
                open=True,
            )
        except VendorLedger.DoesNotExist:
            return Response(
                {"error": "Open vendor ledger entry not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        set_vendor_application(applying_doc, vendor_ledger)

        try:
            applies_to_id = applying_document_no(applying_doc)
            vendor_no = applying_party_no(applying_doc, "vendor")
            if vendor_no:
                clear_applies_to_stamps_for_document(
                    applies_to_id,
                    vendor_no=vendor_no,
                    except_ledger_id=vendor_ledger.id,
                )
            if ledger_entry_allows_applies_to_stamp(vendor_ledger):
                _set_ledger_entry_applies_to_id(vendor_ledger, applies_to_id)
        except ValueError:
            pass

        if isinstance(applying_doc, PaymentJournal):
            serializer = self.get_serializer(applying_doc)
            journal_payload = serializer.data
        else:
            journal_payload = {
                "system_id": str(applying_doc.system_id),
                "application_status": applying_doc.application_status,
                "applies_to_object_id": applying_doc.applies_to_object_id,
                "applies_to_doc_name": applying_doc.applies_to_doc_name,
            }

        return Response(
            {
                "payment_journal": journal_payload,
                "vendor_ledger_id": vendor_ledger.id,
                "vendor_ledger_document_no": vendor_ledger.document_no,
                "applies_to_id": vendor_ledger.applies_to_id,
            }
        )

    @action(detail=False, methods=["post"], url_path="set-ledger-applies-to-id")
    def set_ledger_applies_to_id(self, request):
        """BC Set Applies-to ID — stamp open ledger row with payment document no."""
        ledger_entry_id = request.data.get("ledger_entry_id")
        party = (request.data.get("party") or "vendor").strip().lower()

        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if not ledger_entry_id:
            return Response(
                {"error": "system_id and ledger_entry_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot set Applies-to ID on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            applies_to_id = applying_document_no(applying_doc)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if party == "customer":
            try:
                ledger_entry = CustomerLedgerEntry.objects.get(pk=ledger_entry_id, open=True)
            except CustomerLedgerEntry.DoesNotExist:
                return Response(
                    {"error": "Open customer ledger entry not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            try:
                ledger_entry = VendorLedger.objects.get(pk=ledger_entry_id, open=True)
            except VendorLedger.DoesNotExist:
                return Response(
                    {"error": "Open vendor ledger entry not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if not ledger_entry_allows_applies_to_stamp(ledger_entry):
            return Response(
                {"error": "Applies-to ID cannot be set on payment entries"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_applies_to_id = (ledger_entry.applies_to_id or "").strip()
        if current_applies_to_id == applies_to_id:
            ledger_entry.applies_to_id = ""
            ledger_entry.save(update_fields=["applies_to_id", "updated_at"])
            return Response(
                {
                    "ledger_entry_id": ledger_entry.id,
                    "applies_to_id": "",
                    "document_no": applying_doc.document_no,
                    "cleared": True,
                }
            )

        _set_ledger_entry_applies_to_id(ledger_entry, applies_to_id)

        return Response(
            {
                "ledger_entry_id": ledger_entry.id,
                "applies_to_id": applies_to_id,
                "document_no": applying_doc.document_no,
                "cleared": False,
            }
        )

    @action(detail=False, methods=["post"], url_path="clear-ledger-applies-to-id")
    def clear_ledger_applies_to_id(self, request):
        """BC Applies-to ID OnValidate clear — remove payment stamp from a ledger row."""
        ledger_entry_id = request.data.get("ledger_entry_id")
        party = (request.data.get("party") or "vendor").strip().lower()

        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if not ledger_entry_id:
            return Response(
                {"error": "system_id and ledger_entry_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot clear Applies-to ID on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if party == "customer":
            try:
                ledger_entry = CustomerLedgerEntry.objects.get(pk=ledger_entry_id, open=True)
            except CustomerLedgerEntry.DoesNotExist:
                return Response(
                    {"error": "Open customer ledger entry not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            try:
                ledger_entry = VendorLedger.objects.get(pk=ledger_entry_id, open=True)
            except VendorLedger.DoesNotExist:
                return Response(
                    {"error": "Open vendor ledger entry not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        ledger_entry.applies_to_id = ""
        ledger_entry.save(update_fields=["applies_to_id", "updated_at"])

        return Response(
            {
                "ledger_entry_id": ledger_entry.id,
                "applies_to_id": "",
                "document_no": applying_doc.document_no,
                "cleared": True,
            }
        )

    @action(detail=False, methods=["post"], url_path="clear-applies-to-stamps")
    def clear_applies_to_stamps(self, request):
        """Clear temporary Applies-to ID stamps when closing Apply Entries without posting."""
        party = (request.data.get("party") or "vendor").strip().lower()

        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot clear Applies-to ID on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document_no = applying_document_no(applying_doc)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        vendor_no = applying_party_no(applying_doc, "vendor") if party == "vendor" else None
        customer_no = applying_party_no(applying_doc, "customer") if party == "customer" else None

        cleared_count = clear_applies_to_stamps_for_document(
            document_no,
            vendor_no=vendor_no,
            customer_no=customer_no,
        )

        return Response(
            {
                "document_no": document_no,
                "cleared_count": cleared_count,
            }
        )

    @action(detail=False, methods=["post"], url_path="unapply-vendor-entry")
    def unapply_vendor_entry(self, request):
        """Clear vendor application from a payment journal header."""
        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot unapply entries on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        applies_to_id = (applying_doc.document_no or "").strip()
        linked_id = applying_doc.applies_to_object_id

        clear_application(
            applying_doc,
            linked_ledger_id=linked_id,
            applies_to_id=applies_to_id,
        )

        vendor_no = applying_party_no(applying_doc, "vendor")
        if applies_to_id and vendor_no:
            clear_applies_to_stamps_for_document(applies_to_id, vendor_no=vendor_no)

        if isinstance(applying_doc, PaymentJournal):
            serializer = self.get_serializer(applying_doc)
            return Response(serializer.data)

        return Response(
            {
                "system_id": str(applying_doc.system_id),
                "application_status": applying_doc.application_status,
                "applies_to_object_id": applying_doc.applies_to_object_id,
            }
        )

    @action(detail=False, methods=["post"], url_path="apply-customer-entry")
    def apply_customer_entry(self, request):
        """Apply payment journal header to an open customer ledger entry (BC Apply Customer Entries)."""
        customer_ledger_id = request.data.get("customer_ledger_id")

        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if not customer_ledger_id:
            return Response(
                {"error": "system_id and customer_ledger_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot apply entries on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            customer_ledger = CustomerLedgerEntry.objects.select_related("customer").get(
                pk=customer_ledger_id,
                open=True,
            )
        except CustomerLedgerEntry.DoesNotExist:
            return Response(
                {"error": "Open customer ledger entry not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        set_customer_application(applying_doc, customer_ledger)

        try:
            applies_to_id = applying_document_no(applying_doc)
            customer_no = applying_party_no(applying_doc, "customer")
            if customer_no:
                clear_applies_to_stamps_for_document(
                    applies_to_id,
                    customer_no=customer_no,
                    except_ledger_id=customer_ledger.id,
                )
            if ledger_entry_allows_applies_to_stamp(customer_ledger):
                _set_ledger_entry_applies_to_id(customer_ledger, applies_to_id)
        except ValueError:
            pass

        if isinstance(applying_doc, PaymentJournal):
            serializer = self.get_serializer(applying_doc)
            journal_payload = serializer.data
        else:
            journal_payload = {
                "system_id": str(applying_doc.system_id),
                "application_status": applying_doc.application_status,
                "applies_to_object_id": applying_doc.applies_to_object_id,
                "applies_to_doc_name": applying_doc.applies_to_doc_name,
            }

        return Response(
            {
                "payment_journal": journal_payload,
                "customer_ledger_id": customer_ledger.id,
                "customer_ledger_document_no": customer_ledger.document_no,
                "applies_to_id": customer_ledger.applies_to_id,
            }
        )

    @action(detail=False, methods=["post"], url_path="unapply-customer-entry")
    def unapply_customer_entry(self, request):
        """Clear customer application from a payment journal header."""
        applying_doc, error_response = _load_applying_document(request)
        if error_response:
            return error_response

        if is_applying_document_posted(applying_doc):
            return Response(
                {"error": "Cannot unapply entries on a posted journal line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        applies_to_id = (applying_doc.document_no or "").strip()
        linked_id = applying_doc.applies_to_object_id

        clear_application(
            applying_doc,
            linked_ledger_id=linked_id,
            applies_to_id=applies_to_id,
        )

        customer_no = applying_party_no(applying_doc, "customer")
        if applies_to_id and customer_no:
            clear_applies_to_stamps_for_document(applies_to_id, customer_no=customer_no)

        if isinstance(applying_doc, PaymentJournal):
            serializer = self.get_serializer(applying_doc)
            return Response(serializer.data)

        return Response(
            {
                "system_id": str(applying_doc.system_id),
                "application_status": applying_doc.application_status,
                "applies_to_object_id": applying_doc.applies_to_object_id,
            }
        )

    @action(detail=False, methods=["post"], url_path="quick-customer-payment")
    def quick_customer_payment(self, request):
        """POS one-shot: create customer payment, apply oldest open invoice, and post."""
        from payments.quick_customer_payment import (
            QuickCustomerPaymentError,
            quick_customer_payment as run_quick_customer_payment,
        )

        try:
            create_only = bool(request.data.get("create_only"))
            result = run_quick_customer_payment(
                customer_id=request.data.get("customer_id"),
                amount=request.data.get("amount"),
                payment_method_id=request.data.get("payment_method_id"),
                request=request,
                create_only=create_only,
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except QuickCustomerPaymentError as exc:
            return Response(
                {"error": exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                "Error in quick-customer-payment: %s", str(e), exc_info=True
            )
            return Response(
                {"error": f"Failed to record payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def post_payment_journal(self, request, pk=None):
        """Post a payment journal entry"""
        try:
            payment_journal = self.get_object()

            # Check if already posted
            if payment_journal.status == "Posted":
                return Response(
                    {"error": "Payment journal has already been posted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Use the custom user model as specified in cursor rules
            user = CustomUser.objects.filter(is_superuser=True).first()
            if not user:
                return Response(
                    {"error": "No superuser found for posting"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            try:
                # Validate tracking specifications for all lines before posting
                payment_journal.full_clean()
                payment_journal.clean()  # Custom model validation

                # Create posting processor and post the payment journal
                from .admin import PaymentJournalPostingProcessor

                processor = PaymentJournalPostingProcessor(
                    payment_journal, request, receipt_no
                )

                # Start transaction to ensure all entries are created or none are
                with transaction.atomic():
                    result = processor.post()

                    if result["success"]:
                        # Update the payment journal status to Posted
                        payment_journal.status = "Posted"
                        payment_journal.save()

                        serializer = self.get_serializer(payment_journal)
                        return Response(serializer.data)
                    else:
                        error_msg = result.get(
                            "message", "Unknown error during posting"
                        )
                        return Response(
                            {"error": error_msg},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except Exception as e:
                error_msg = str(e)
                # Clean up redundant prefixes
                if error_msg.startswith("Error posting payment journal: "):
                    error_msg = error_msg.replace("Error posting payment journal: ", "")
                if error_msg.startswith("Error processing payment journal: "):
                    error_msg = error_msg.replace(
                        "Error processing payment journal: ", ""
                    )

                return Response(
                    {"error": error_msg},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Error posting payment journal {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to post payment journal: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
