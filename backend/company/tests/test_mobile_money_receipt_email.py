from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from company.admin import BillingHistoryAdmin
from company.billing_receipt_email import (
    generate_invoice_pdf_bytes,
    generate_receipt_pdf_bytes,
    send_verified_mobile_money_subscription_receipt,
)
from company.models import PaymentGateway
from core.email_backends import MailtrapSendAPIBackend


def _make_billing(payment_type=None, payer_email="payer@example.com", user_reference=None):
    metadata = {"payer_email": payer_email}
    if payment_type:
        metadata["payment_type"] = payment_type
    if user_reference:
        metadata["user_reference"] = user_reference
    return SimpleNamespace(
        metadata=metadata,
        status="paid",
        reference_number="#36002",
        gateway_payment_id="ZENTRO-ABC-123",
        company=SimpleNamespace(name="Demo Co", email="company@example.com"),
        product="Standard",
        currency="UGX",
        amount=20000,
        billing_date=date(2026, 4, 16),
        verified_at=SimpleNamespace(isoformat=lambda: "2026-04-16T10:00:00+00:00"),
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BillingReceiptEmailServiceTests(SimpleTestCase):
    def test_sends_with_two_pdf_attachments_to_payer(self):
        billing = _make_billing()
        sent = send_verified_mobile_money_subscription_receipt(billing)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["payer@example.com"])
        self.assertEqual(len(msg.attachments), 2)
        self.assertTrue(msg.attachments[0][0].startswith("invoice-"))
        self.assertTrue(msg.attachments[1][0].startswith("receipt-"))

    def test_falls_back_to_company_email(self):
        billing = _make_billing(payer_email="")
        sent = send_verified_mobile_money_subscription_receipt(billing)
        self.assertTrue(sent)
        self.assertEqual(mail.outbox[0].to, ["company@example.com"])

    def test_skips_extra_users_payment(self):
        billing = _make_billing(payment_type="extra_users")
        sent = send_verified_mobile_money_subscription_receipt(billing)
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_generate_invoice_and_receipt_pdf_magic_bytes(self):
        billing = _make_billing()
        inv = generate_invoice_pdf_bytes(billing)
        rec = generate_receipt_pdf_bytes(billing)
        self.assertTrue(inv.startswith(b"%PDF"))
        self.assertTrue(rec.startswith(b"%PDF"))
        self.assertGreater(len(inv), 500)
        self.assertGreater(len(rec), 500)

    def test_sent_email_attachments_are_valid_pdfs(self):
        billing = _make_billing()
        send_verified_mobile_money_subscription_receipt(billing)
        msg = mail.outbox[0]
        for filename, content, mimetype in msg.attachments:
            self.assertEqual(mimetype, "application/pdf")
            self.assertTrue(content.startswith(b"%PDF"), filename)

    def test_pdf_generation_with_customer_transaction_in_metadata(self):
        billing = _make_billing(user_reference="40223076804")
        inv = generate_invoice_pdf_bytes(billing)
        rec = generate_receipt_pdf_bytes(billing)
        self.assertTrue(inv.startswith(b"%PDF"))
        self.assertTrue(rec.startswith(b"%PDF"))


class BillingHistoryAdminVerifyActionTests(SimpleTestCase):
    @patch("company.admin.models.Subscription.objects.get")
    @patch("company.billing_receipt_email.send_verified_mobile_money_subscription_receipt")
    @patch("company.views.activate_subscription_from_billing", return_value=(True, "subscription"))
    @patch("company.admin.timezone.now")
    @patch("company.admin.schema_context")
    def test_verify_action_sends_receipt_for_subscription(
        self,
        mock_schema_context,
        mock_now,
        _mock_activate,
        mock_send_receipt,
        mock_get_subscription,
    ):
        @contextmanager
        def _ctx(*args, **kwargs):
            yield

        mock_schema_context.side_effect = _ctx
        mock_now.return_value = "now"
        mock_get_subscription.return_value = MagicMock()

        billing = MagicMock()
        billing.status = "pending_verification"
        billing.payment_gateway = PaymentGateway.MANUAL_MOBILE_MONEY
        billing.company = SimpleNamespace()
        billing.reference_number = "#36010"
        billing.billing_date = "2026-04-16"

        model_admin = BillingHistoryAdmin(model=MagicMock(), admin_site=MagicMock())
        model_admin.verify_payment_action(MagicMock(), [billing])

        self.assertEqual(billing.status, "paid")
        self.assertTrue(mock_send_receipt.called)

    @patch("company.admin.models.Subscription.objects.get")
    @patch("company.billing_receipt_email.send_verified_mobile_money_subscription_receipt")
    @patch("company.views.activate_subscription_from_billing", return_value=(True, "extra_users"))
    @patch("company.admin.timezone.now")
    @patch("company.admin.schema_context")
    def test_verify_action_keeps_running_when_email_send_fails(
        self,
        mock_schema_context,
        mock_now,
        _mock_activate,
        mock_send_receipt,
        mock_get_subscription,
    ):
        @contextmanager
        def _ctx(*args, **kwargs):
            yield

        mock_schema_context.side_effect = _ctx
        mock_now.return_value = "now"
        mock_get_subscription.return_value = MagicMock()
        mock_send_receipt.side_effect = RuntimeError("send failed")

        billing = MagicMock()
        billing.status = "pending_verification"
        billing.payment_gateway = PaymentGateway.MANUAL_MOBILE_MONEY
        billing.company = SimpleNamespace()
        billing.reference_number = "#36011"
        billing.billing_date = "2026-04-16"

        model_admin = BillingHistoryAdmin(model=MagicMock(), admin_site=MagicMock())
        model_admin.verify_payment_action(MagicMock(), [billing])
        self.assertEqual(billing.status, "paid")


class MailtrapAttachmentPayloadTests(SimpleTestCase):
    @patch("core.email_backends.requests.post")
    def test_mailtrap_backend_serializes_attachments(self, mock_post):
        response = MagicMock()
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        message = EmailMultiAlternatives(
            subject="Test",
            body="Plain",
            from_email="from@example.com",
            to=["to@example.com"],
        )
        message.attach("receipt.pdf", b"%PDF-1.4", "application/pdf")

        backend = MailtrapSendAPIBackend(api_key="token")
        sent = backend._send_one(message)

        self.assertTrue(sent)
        kwargs = mock_post.call_args.kwargs
        payload = kwargs["json"]
        self.assertIn("attachments", payload)
        self.assertEqual(len(payload["attachments"]), 1)
        self.assertEqual(payload["attachments"][0]["filename"], "receipt.pdf")
