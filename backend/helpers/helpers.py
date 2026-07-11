# from setup.models import EmailSetup, EmailCategory
import random
import json
import os
import requests
import html
from typing import Optional, List

from django_tenants.utils import schema_context
from django.conf import settings
from django.core.mail import send_mail

# Mailtrap Transactional Send API (same as scripts/send-mailtrap-curl.sh)
MAILTRAP_SEND_API_URL = "https://send.api.mailtrap.io/api/send"


def _send_via_mailtrap_send_api(
    subject: str,
    text: str,
    from_email: str,
    to_emails: List[str],
    html_content: Optional[str] = None,
) -> bool:
    """Send one email via POST send.api.mailtrap.io/api/send (same approach as curl script)."""
    api_key = (
        getattr(settings, "MAILTRAP_SEND_API_KEY", "") or ""
    ).strip() or (getattr(settings, "EMAIL_HOST_API_KEY", "") or "").strip()
    if not api_key:
        return False
    from_addr = from_email if "@" in from_email else from_email.strip()
    if " <" in from_addr and ">" in from_addr:
        from_addr = from_addr.split("<", 1)[1].split(">", 1)[0].strip()
    payload = {
        "from": {"email": from_addr},
        "to": [{"email": addr} for addr in to_emails],
        "subject": subject,
        "text": text or "",
    }
    if html_content:
        payload["html"] = html_content
    try:
        r = requests.post(
            MAILTRAP_SEND_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        r.raise_for_status()
        return True
    except requests.RequestException as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Mailtrap Send API request failed: %s", exc
        )
        return False
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.db import connection
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


from setup.models import (
    EmailSetup,
    EmailCategory,
    NoSeries,
    NoSeriesLines,
    InventorySetup,
    JournalSetup,
    ManufacturingSetup,
)
from authentication.models import OTP
from setup.enums import JournalType


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors"""

    def __init__(self, message, setup_type=None, field_name=None):
        self.message = message
        self.setup_type = setup_type
        self.field_name = field_name
        super().__init__(self.message)


def _store_verification_otp(user, schema_name: str, otp: str) -> None:
    with schema_context(schema_name):
        if not OTP.objects.filter(user=user).exists():
            otp_obj = OTP.objects.create(user=user)
        else:
            otp_obj = OTP.objects.get(user=user)
        otp_obj.set_otp(otp)


def _dispatch_verification_email(email: str, user, otp: str) -> bool:
    """Deliver a pre-generated OTP by email (no DB write)."""
    import logging

    from helpers.send_email import send_transactional_email

    logger = logging.getLogger(__name__)

    logo_url = getattr(
        settings,
        "ZENTRO_EMAIL_LOGO_URL",
        "https://zentroapp.app/img/logo/logo-light-streamline.png",
    )
    html_content = render_to_string(
        "email_verification.html",
        {"otp": otp, "username": user.email, "logo_url": logo_url},
    )

    subject = "Verify your Zentro account"
    plain_message = (
        f"Hi,\n\nYour verification code is: {otp}\n\n"
        "It expires in 5 minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )

    if send_transactional_email(
        to=email,
        subject=subject,
        html=html_content,
        plain_message=plain_message,
    ):
        logger.info("Verification OTP email sent to %s", email)
        return True

    logger.error("Failed to send verification email to %s", email)
    if getattr(settings, "DEBUG", False):
        logger.warning("[DEV] Verification OTP for %s: %s", email, otp)
    return False


def _dispatch_verification_sms(phone: str, user, otp: str) -> bool:
    """Deliver a pre-generated OTP by SMS (no DB write)."""
    import logging

    logger = logging.getLogger(__name__)

    display_name = (
        getattr(user, "full_name", None)
        or getattr(user, "username", None)
        or "there"
    )
    message = (
        f"Hi {display_name}, your Zentro verification code is {otp}. "
        "It expires in 5 minutes."
    )

    if send_plain_sms(phone, message):
        logger.info("Verification OTP SMS sent to %s", phone)
        return True

    logger.error("Failed to send verification SMS to %s", phone)
    if getattr(settings, "DEBUG", False):
        logger.warning("[DEV] Verification OTP for %s: %s", phone, otp)
    return False


def send_verification_otp(user, schema_name: str) -> dict:
    """
    Generate one OTP and deliver it via email and SMS (when phone is on file).
    Returns {"email": bool, "sms": bool, "success": bool}.
    """
    otp = generate_random_code(6)
    _store_verification_otp(user, schema_name, otp)

    email_ok = False
    sms_ok = False

    if getattr(user, "email", None):
        email_ok = _dispatch_verification_email(user.email, user, otp)

    phone = (getattr(user, "phone_number", None) or "").strip()
    if phone:
        sms_ok = _dispatch_verification_sms(phone, user, otp)

    return {
        "email": email_ok,
        "sms": sms_ok,
        "success": email_ok or sms_ok,
    }


def send_verification_email(email, user, schema_name) -> bool:
    """
    Send account verification OTP via email (and SMS when the user has a phone).
    """
    result = send_verification_otp(user, schema_name)
    return result["success"]


def send_verification_sms(phone: str, user, schema_name: str) -> bool:
    """
    Send account verification OTP via SMS (and email when the user has an email).
    """
    result = send_verification_otp(user, schema_name)
    return result["success"]


def send_forgot_password_link_email(
    email: str, user, schema_name: str, reset_url: str
) -> bool:
    """
    Send password reset link to user's email via Mailtrap.

    Args:
        email: Recipient email address.
        user: User instance (CustomUser).
        schema_name: Tenant schema name.
        reset_url: Full URL for the reset password page (includes token).

    Returns:
        True if email sent successfully, False otherwise.
    """
    import logging

    logger = logging.getLogger(__name__)

    html_content = render_to_string(
        "password_reset_link.html",
        {"username": user.email, "reset_url": reset_url},
    )

    subject = "Reset Your Zentro Password"
    plain_message = (
        f"Hi {user.email},\n\n"
        "We received a request to reset your password. "
        f"Click the link below to set a new password (expires in 1 hour):\n\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@zentroapp.app")

    # Use Mailtrap Send API (same as send-mailtrap-curl.sh) when token is set
    api_key = (
        getattr(settings, "MAILTRAP_SEND_API_KEY", "") or getattr(settings, "EMAIL_HOST_API_KEY", "") or ""
    ).strip()
    if api_key:
        try:
            if _send_via_mailtrap_send_api(
                subject, plain_message, from_email, [email], html_content=html_content
            ):
                return True
        except Exception as e:
            logger.exception(f"Mailtrap Send API failed for password reset to {email}: {e}")

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.exception(f"Failed to send password reset email to {email}: {e}")
        return False


def send_forgot_password_otp_email(email: str, user, schema_name: str) -> bool:
    """
    Send OTP to user's email for password reset via Mailtrap (Django EMAIL_BACKEND).
    Creates/updates OTP for the user and sends the OTP email.

    Args:
        email: Recipient email address.
        user: User instance (CustomUser).
        schema_name: Tenant schema name for OTP storage.

    Returns:
        True if email sent successfully, False otherwise.
    """
    import logging

    logger = logging.getLogger(__name__)

    otp = generate_random_code(6)

    with schema_context(schema_name):
        if not OTP.objects.filter(user=user).exists():
            otp_obj = OTP.objects.create(user=user)
        else:
            otp_obj = OTP.objects.get(user=user)
        otp_obj.set_otp(otp)

    html_content = render_to_string(
        "password_reset_otp.html",
        {"otp": otp, "username": user.email},
    )

    subject = "Reset Your Password - OTP"
    plain_message = f"Your password reset OTP is: {otp}. It expires in 10 minutes."
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@zentroapp.app")

    # Use Mailtrap Send API (same as send-mailtrap-curl.sh) when token is set
    api_key = (
        getattr(settings, "MAILTRAP_SEND_API_KEY", "") or getattr(settings, "EMAIL_HOST_API_KEY", "") or ""
    ).strip()
    if api_key:
        try:
            if _send_via_mailtrap_send_api(
                subject, plain_message, from_email, [email], html_content=html_content
            ):
                return True
        except Exception as e:
            logger.exception(f"Mailtrap Send API failed for OTP to {email}: {e}")

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.exception(f"Failed to send forgot-password OTP to {email}: {e}")
        if getattr(settings, "DEBUG", False):
            logger.warning(f"[DEV] Use this OTP for {email}: {otp}")
        return False


def send_plain_sms(phone: str, message: str) -> Optional[str]:
    """
    Send a simple SMS message (not tied to OTP) using the Egosms API.

    Args:
        phone: Recipient phone in international format, e.g. '+256750440865' or '256750440865'.
        message: SMS body text.

    Returns:
        Response text from provider if successful, otherwise None.
    """
    try:
        # Normalize phone by removing leading '+' if present
        normalized_phone = phone[1:] if phone.startswith("+") else phone

        api_url = "https://www.egosms.co/api/v1/plain/"
        username = "jom"
        password = "5u2kCM2jb6@yQyc"
        sender = "Egosms"

        params = {
            "username": html.escape(username),
            "password": html.escape(password),
            "number": html.escape(normalized_phone),
            "message": html.escape(message),
            "sender": html.escape(sender),
        }

        timeout = 5
        response = requests.get(api_url, params=params, timeout=timeout)
        response.raise_for_status()
        print(f"Plain SMS sent to {normalized_phone}")
        return response.text
    except requests.RequestException as e:
        print(f"Failed to send plain SMS to {phone}. Reason: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error sending plain SMS: {str(e)}")
        return None


def send_email(email):
    try:
        with schema_context("public"):
            email_setup = EmailSetup.objects.get(
                email_category=EmailCategory.VERIFICATION.value
            )
        settings.EMAIL_HOST = email_setup.email_host
        settings.EMAIL_HOST_USER = email_setup.email_host_user
        settings.EMAIL_HOST_PASSWORD = email_setup.email_host_password
        settings.EMAIL_PORT = email_setup.email_port
        settings.EMAIL_USE_TLS = email_setup.email_use_tls

        subject = "News letter"
        message = "This is a monthly news letter from Zentroap"
        html_content = "This is a monthly news letter from Zentroap"

        send_mail(
            subject,
            message,
            email_setup.email_host_user,
            [email],
            html_message=html_content,
        )
        current_month = datetime.now().strftime("%B")

        return f"current_month {current_month} news letter sent"
    except Exception as e:
        print(e)


def generate_random_code(length):
    #     # define the characters to use
    chars = "0123456789"

    # keep generating codes until we find one that hasn't been used before
    while True:
        code = "".join(random.choice(chars) for _ in range(length))
        if code:
            break
        # if not OTP.objects.filter(otp=code).exists():
        #     break

    return code


def setup_default_no_series():
    """
    This function is used to setup the default no-series for the new company
    """
    print("----------------------------------")
    print("setup_default_no_series")
    print("----------------------------------")
    config_file_path = os.path.join(settings.BASE_DIR, "data", "default_no_series.json")
    with open(config_file_path, "r") as file:
        config = json.load(file)
    series_mapping = {}
    for series in config["no_series"]:
        # Use get_or_create to handle cases where NoSeries already exists
        # (e.g., POSTPREPINV and POSTPREPCM created by seed_prepayment_no_series)
        no_series, created = NoSeries.objects.get_or_create(
            code=series["code"], defaults={"description": series["description"]}
        )

        # Update description if it exists but description is different
        if not created and no_series.description != series["description"]:
            no_series.description = series["description"]
            no_series.save(update_fields=["description"])

        series_mapping[series["code"]] = no_series

        # Use get_or_create for NoSeriesLines as well to handle existing records
        no_series_line, line_created = NoSeriesLines.objects.get_or_create(
            no_series=no_series,
            defaults={
                "start_number": series["no_series_lines"]["start_number"],
                "increment_by": series["no_series_lines"]["increment_by"],
            },
        )

        # Update NoSeriesLines if it exists but fields are missing or different
        if not line_created:
            updated_fields = []
            if (
                not no_series_line.start_number
                or no_series_line.start_number
                != series["no_series_lines"]["start_number"]
            ):
                no_series_line.start_number = series["no_series_lines"]["start_number"]
                updated_fields.append("start_number")
            if (
                not no_series_line.increment_by
                or no_series_line.increment_by
                != series["no_series_lines"]["increment_by"]
            ):
                no_series_line.increment_by = series["no_series_lines"]["increment_by"]
                updated_fields.append("increment_by")
            if updated_fields:
                no_series_line.save(update_fields=updated_fields)

    InventorySetup.objects.create(
        item_no_series=series_mapping["ITM"],
    )

    try:
        # Create Item Journal Setup
        JournalSetup.objects.create(
            journal_no_series=series_mapping["ITMJ"],
            journal_type=JournalType.ITEM.value,
        )

        # Create Payment Journal Setup
        JournalSetup.objects.create(
            journal_no_series=series_mapping["PAYMENT"],
            journal_type=JournalType.PAYMENT.value,
        )

        # Create Expense Journal Setup
        JournalSetup.objects.create(
            journal_no_series=series_mapping["EXP"],
            journal_type=JournalType.EXPENSE.value,
        )

        # Create Manufacturing Setup (if BOM or PRODBOM series exists)
        # Prefer PRODBOM over BOM for Production BOM
        bom_series = series_mapping.get("PRODBOM") or series_mapping.get("BOM")
        if bom_series:
            manufacturing_setup, created = ManufacturingSetup.objects.get_or_create(
                defaults={
                    "bom_no_series": bom_series,
                    "production_order_no_series": series_mapping.get("PROD"),
                    "work_center_no_series": series_mapping.get("WORKCTR"),
                    "machine_center_no_series": series_mapping.get("MACHCTR"),
                    "routing_no_series": series_mapping.get("ROUTING"),
                }
            )
            # Update if it already exists but fields are missing
            updated_fields = []
            # Update BOM series if PRODBOM is available and BOM is currently set
            if (
                not created
                and manufacturing_setup.bom_no_series_id
                and "PRODBOM" in series_mapping
                and manufacturing_setup.bom_no_series.code == "BOM"
            ):
                manufacturing_setup.bom_no_series = series_mapping["PRODBOM"]
                updated_fields.append("bom_no_series")
            elif (
                not created and not manufacturing_setup.bom_no_series_id and bom_series
            ):
                manufacturing_setup.bom_no_series = bom_series
                updated_fields.append("bom_no_series")
            if (
                not created
                and not manufacturing_setup.production_order_no_series_id
                and "PROD" in series_mapping
            ):
                manufacturing_setup.production_order_no_series = series_mapping["PROD"]
                updated_fields.append("production_order_no_series")
            if (
                not created
                and not manufacturing_setup.work_center_no_series_id
                and "WORKCTR" in series_mapping
            ):
                manufacturing_setup.work_center_no_series = series_mapping["WORKCTR"]
                updated_fields.append("work_center_no_series")
            if (
                not created
                and not manufacturing_setup.machine_center_no_series_id
                and "MACHCTR" in series_mapping
            ):
                manufacturing_setup.machine_center_no_series = series_mapping["MACHCTR"]
                updated_fields.append("machine_center_no_series")
            if (
                not created
                and not manufacturing_setup.routing_no_series_id
                and "ROUTING" in series_mapping
            ):
                manufacturing_setup.routing_no_series = series_mapping["ROUTING"]
                updated_fields.append("routing_no_series")
            if updated_fields:
                manufacturing_setup.save(update_fields=updated_fields)

        return "Default no-series setup completed"
    except Exception as e:
        print(f"Error in setup_default_no_series: {str(e)}")
        print(f"Current schema: {connection.schema_name}")  # Add this for debugging
        raise


def increment_item_number(last_number: str, increment_by: int = 1) -> str:
    """
    Increment the numeric part of an item number while preserving the prefix format.
    Example: If last_number is 'ITM-000001' -> returns 'ITM-000002'
             If last_number is 'JRN-000001' -> returns 'JRN-000002'

    Args:
        last_number (str): The item number to be incremented (e.g., 'ITM-000001', 'JRN-000001').
        increment_by (int): The value to increment the numeric part by. Defaults to 1.

    Returns:
        str: The incremented item number with the original format preserved.
    """
    try:
        # Find the position of the hyphen
        hyphen_pos = last_number.find("-")
        if hyphen_pos == -1:
            raise ValueError(f"Invalid number format: {last_number}")

        # Split into prefix and number parts
        prefix = last_number[: hyphen_pos + 1]  # Include the hyphen
        number_str = last_number[hyphen_pos + 1 :]

        # Convert to integer and increment
        current_number = int(number_str)
        new_number = current_number + increment_by

        # Use the same padding length as the input
        padding_length = len(number_str)
        formatted_number = str(new_number).zfill(padding_length)

        # Combine original prefix and formatted number
        new_item_number = f"{prefix}{formatted_number}"

        return new_item_number

    except (ValueError, IndexError) as e:
        raise ValueError(f"Error incrementing number {last_number}: {str(e)}")


def to_camel_case(text: str) -> str:

    # Remove any extra spaces and split into words
    words = text.strip().split()

    # Capitalize first letter of each word and join
    return "".join(word.capitalize() for word in words)


def generate_document_number(
    setup_model_class,
    setup_field_name: str,
    no_series_field_name: str,
    is_no_series_lines: bool = False,
) -> tuple:
    """
    Generic function to generate document numbers using NoSeriesLines.

    Args:
        setup_model_class: The setup model class (e.g., PurchasePayable, JournalSetup)
        setup_field_name: The field name in the setup model that contains the NoSeriesLines reference
        no_series_field_name: The field name to set the generated number to (e.g., 'invoice_no', 'document_no')
        is_no_series_lines: If True, setup_field_name points to NoSeriesLines directly.
                           If False, setup_field_name points to NoSeries and we need to get NoSeriesLines

    Returns:
        tuple: (generated_number, updated_no_series_lines_object)

    Raises:
        ConfigurationError: If the required configuration is missing
    """
    from django.db import transaction
    from django.utils.timezone import datetime

    setup_instance = setup_model_class.objects.all().first()
    if not setup_instance:
        error_msg = f"No {setup_model_class.__name__} configuration found. Please configure the {setup_model_class.__name__} settings first."
        raise ConfigurationError(error_msg, setup_model_class.__name__)

    # Get the field from the setup
    setup_field = getattr(setup_instance, setup_field_name)
    if not setup_field:
        error_msg = f"Field '{setup_field_name}' is not configured in {setup_model_class.__name__}. Please check your setup configuration."
        raise ConfigurationError(
            error_msg, setup_model_class.__name__, setup_field_name
        )

    # Get the NoSeriesLines object
    if is_no_series_lines:
        # setup_field is already a NoSeriesLines object
        no_series_lines = setup_field
    else:
        # setup_field is a NoSeries object, so we need to get the NoSeriesLines
        no_series_lines = NoSeriesLines.objects.filter(no_series=setup_field).first()

    if not no_series_lines:
        error_msg = f"No number series configuration found for {setup_field_name}. Please configure the number series first."
        raise ConfigurationError(
            error_msg, setup_model_class.__name__, setup_field_name
        )

    with transaction.atomic():
        increment_by = no_series_lines.increment_by

        if no_series_lines.last_used_number:
            # Generate new number using existing logic
            generated_number = increment_item_number(
                no_series_lines.last_used_number, increment_by
            )
        else:
            # Use start number if no previous number exists
            generated_number = no_series_lines.start_number

        # Update the NoSeriesLines object
        no_series_lines.last_used_number = generated_number
        no_series_lines.last_used_date = datetime.now()
        no_series_lines.save()

        return generated_number, no_series_lines
