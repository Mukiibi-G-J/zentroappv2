"""
Generic transactional email helper using Django's EMAIL_BACKEND (Mailtrap).
Replaces Resend - all emails now go through Mailtrap SMTP.
"""

import logging
from typing import List, Optional, Union

from django.conf import settings
from django.core.mail import EmailMessage, send_mail

logger = logging.getLogger(__name__)


def send_transactional_email(
    to: Union[str, List[str]],
    subject: str,
    html: str,
    plain_message: Optional[str] = None,
    from_email: Optional[str] = None,
    bcc: Optional[Union[str, List[str]]] = None,
) -> bool:
    """
    Send an email via Django's EMAIL_BACKEND (Mailtrap).

    Args:
        to: Recipient email(s) - string or list of strings
        subject: Email subject
        html: HTML body content
        plain_message: Optional plain text fallback (defaults to stripped HTML)
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        bcc: Optional BCC recipient(s) - string or list of strings

    Returns:
        True if sent successfully, False otherwise.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    sender = from_email or getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@zentroapp.app"
    )
    plain = plain_message or ""

    try:
        if bcc:
            bcc_list = [bcc] if isinstance(bcc, str) else list(bcc)
            msg = EmailMessage(
                subject=subject,
                body=plain,
                from_email=sender,
                to=recipients,
                bcc=bcc_list,
            )
            msg.content_subtype = "html"
            msg.body = html
            msg.send(fail_silently=False)
        else:
            send_mail(
                subject,
                plain,
                sender,
                recipients,
                html_message=html,
                fail_silently=False,
            )
        logger.info(f"Email sent successfully to {recipients}")
        return True
    except Exception as e:
        logger.exception(f"Email failed to {recipients}: {e}")
        return False
