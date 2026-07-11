"""
Custom email backends for Mailtrap.

- MailtrapSendAPIBackend: POST to https://send.api.mailtrap.io/api/send (same as scripts/send-mailtrap-curl.sh).
- MailtrapEmailBackend: SMTP with Python 3.13 compatibility (initial_response_ok=False).
"""

import email.utils
import base64
import smtplib
import ssl
import threading

import requests

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
from django.core.mail.utils import DNS_NAME
from django.utils.functional import cached_property


class MailtrapEmailBackend(BaseEmailBackend):
    """
    SMTP backend that uses initial_response_ok=False for Python 3.13 compatibility
    with Mailtrap and other servers that may close the connection during
    the default AUTH flow.
    """

    def __init__(
        self,
        host=None,
        port=None,
        username=None,
        password=None,
        use_tls=None,
        fail_silently=False,
        use_ssl=None,
        timeout=None,
        ssl_keyfile=None,
        ssl_certfile=None,
        **kwargs,
    ):
        super().__init__(fail_silently=fail_silently)
        self.host = host or settings.EMAIL_HOST
        self.port = port or settings.EMAIL_PORT
        self.username = settings.EMAIL_HOST_USER if username is None else username
        self.password = settings.EMAIL_HOST_PASSWORD if password is None else password
        self.use_tls = settings.EMAIL_USE_TLS if use_tls is None else use_tls
        self.use_ssl = settings.EMAIL_USE_SSL if use_ssl is None else use_ssl
        self.timeout = settings.EMAIL_TIMEOUT if timeout is None else timeout
        self.ssl_keyfile = (
            settings.EMAIL_SSL_KEYFILE if ssl_keyfile is None else ssl_keyfile
        )
        self.ssl_certfile = (
            settings.EMAIL_SSL_CERTFILE if ssl_certfile is None else ssl_certfile
        )
        if self.use_ssl and self.use_tls:
            raise ValueError(
                "EMAIL_USE_TLS/EMAIL_USE_SSL are mutually exclusive, so only set "
                "one of those settings to True."
            )
        self.connection = None
        self._lock = threading.RLock()

    @property
    def connection_class(self):
        return smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

    @cached_property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        else:
            return ssl.create_default_context()

    def open(self):
        if self.connection:
            return False

        connection_params = {"local_hostname": DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        if self.use_ssl:
            connection_params["context"] = self.ssl_context
        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )

            if not self.use_ssl and self.use_tls:
                self.connection.starttls(context=self.ssl_context)
            if self.username and self.password:
                self.connection.login(
                    self.username, self.password, initial_response_ok=False
                )
            return True
        except OSError:
            if not self.fail_silently:
                raise

    def close(self):
        if self.connection is None:
            return
        try:
            try:
                self.connection.quit()
            except (ssl.SSLError, smtplib.SMTPServerDisconnected):
                self.connection.close()
            except smtplib.SMTPException:
                if self.fail_silently:
                    return
                raise
        finally:
            self.connection = None

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        with self._lock:
            new_conn_created = self.open()
            if not self.connection or new_conn_created is None:
                return 0
            num_sent = 0
            try:
                for message in email_messages:
                    sent = self._send(message)
                    if sent:
                        num_sent += 1
            finally:
                if new_conn_created:
                    self.close()
        return num_sent

    def _send(self, email_message):
        if not email_message.recipients():
            return False
        encoding = email_message.encoding or settings.DEFAULT_CHARSET
        from_email = sanitize_address(email_message.from_email, encoding)
        recipients = [
            sanitize_address(addr, encoding) for addr in email_message.recipients()
        ]
        message = email_message.message()
        try:
            self.connection.sendmail(
                from_email, recipients, message.as_bytes(linesep="\r\n")
            )
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
            return False
        return True


# -----------------------------------------------------------------------------
# Mailtrap Transactional Send API (same approach as scripts/send-mailtrap-curl.sh)
# POST https://send.api.mailtrap.io/api/send with Bearer token + JSON body
# -----------------------------------------------------------------------------

MAILTRAP_SEND_API_URL = "https://send.api.mailtrap.io/api/send"


def _parse_email_address(addr):
    """Return (email, name) for a string like 'noreply@zentroapp.app' or 'Name <noreply@zentroapp.app>'."""
    if not addr:
        return "", ""
    parsed = email.utils.parseaddr(addr)
    return (parsed[1] or addr.strip(), parsed[0] or "")


class MailtrapSendAPIBackend(BaseEmailBackend):
    """
    Send email via Mailtrap Transactional API (POST send.api.mailtrap.io/api/send).
    Same approach as scripts/send-mailtrap-curl.sh. No sandbox; delivers to real inboxes.
    """

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = (api_key or getattr(settings, "MAILTRAP_SEND_API_KEY", "") or "").strip()
        if not self.api_key:
            self.api_key = (
                getattr(settings, "EMAIL_HOST_API_KEY", "") or ""
            ).strip()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        num_sent = 0
        for message in email_messages:
            if self._send_one(message):
                num_sent += 1
        return num_sent

    def _send_one(self, email_message):
        if not email_message.recipients():
            return False
        encoding = email_message.encoding or settings.DEFAULT_CHARSET
        from_email = sanitize_address(email_message.from_email, encoding)
        from_addr, from_name = _parse_email_address(from_email)
        to_list = [
            {"email": sanitize_address(addr, encoding)}
            for addr in email_message.recipients()
        ]
        payload = {
            "from": {"email": from_addr},
            "to": to_list,
            "subject": email_message.subject,
        }
        if from_name:
            payload["from"]["name"] = from_name
        # Plain text body (required by Mailtrap if no html)
        payload["text"] = email_message.body or ""
        # HTML alternative if present
        html_content = None
        if getattr(email_message, "alternatives", None):
            for content, mimetype in email_message.alternatives:
                if mimetype == "text/html":
                    html_content = content
                    break
        if html_content:
            payload["html"] = html_content
        attachments_payload = []
        for attachment in getattr(email_message, "attachments", []):
            if not isinstance(attachment, tuple) or len(attachment) != 3:
                continue
            filename, content, mimetype = attachment
            if not filename or content is None:
                continue
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content
            attachments_payload.append(
                {
                    "filename": filename,
                    "content": base64.b64encode(content_bytes).decode("ascii"),
                    "type": mimetype or "application/octet-stream",
                    "disposition": "attachment",
                }
            )
        if attachments_payload:
            payload["attachments"] = attachments_payload
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(
                MAILTRAP_SEND_API_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            r.raise_for_status()
            return True
        except requests.RequestException:
            if not self.fail_silently:
                raise
            return False
