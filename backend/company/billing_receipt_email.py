import logging
from datetime import date, datetime
from html import escape as html_escape
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from company.subscription_billing import coverage_period_label
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape as xml_escape

logger = logging.getLogger(__name__)

# Zentro brand — subscription invoice / receipt PDFs (match logo & marketing)
_BRAND_BAR = colors.HexColor("#006D68")  # top bar (pine teal)
_BRAND_ACCENT = colors.HexColor("#40C4D4")  # footer accent stripe (cyan)
_BRAND_DARK = colors.HexColor("#004B7C")  # document title (navy)
_MUTED = colors.HexColor("#5C6B7A")  # labels, subtitle, footer (medium grey)
_MUTED_HEX = "#5C6B7A"  # same, for <font color=""> in PDF cells
_TABLE_ALT_BG = colors.HexColor("#f3f6f8")
_TABLE_RULE = colors.HexColor("#dde5ea")


def _resolve_payer_email(billing_history):
    metadata = billing_history.metadata or {}
    payer_email = (metadata.get("payer_email") or "").strip()
    if payer_email:
        return payer_email
    return (billing_history.company.email or "").strip()


def _is_extra_users_payment(billing_history):
    metadata = billing_history.metadata or {}
    return metadata.get("payment_type") == "extra_users"


def _format_currency(amount, currency):
    return f"{currency} {amount:,.2f}"


def _logo_path():
    p = Path(settings.BASE_DIR) / "static" / "images" / "logo" / "logo-light-full.png"
    if p.is_file():
        return p
    return None


def _make_logo_pdf_image(max_width):
    """
    Build a ReportLab Image with correct aspect ratio and orientation.

    Some PNGs carry EXIF orientation or confuse ReportLab's reader when only
    `width` is passed, which can produce stretched or rotated logos in PDFs.
    """
    logo_file = _logo_path()
    if not logo_file:
        return None
    try:
        from PIL import Image as PILImage
        from PIL import ImageOps
    except ImportError:
        logger.warning("Pillow not available; skipping PDF logo embedding")
        return None

    try:
        with PILImage.open(logo_file) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA") or (
                im.mode == "P" and "transparency" in im.info
            ):
                im = im.convert("RGBA")
                background = PILImage.new("RGB", im.size, (255, 255, 255))
                background.paste(im, mask=im.split()[3])
                im = background
            elif im.mode != "RGB":
                im = im.convert("RGB")

            png_buf = BytesIO()
            im.save(png_buf, format="PNG")
            png_bytes = png_buf.getvalue()

        reader = ImageReader(BytesIO(png_bytes))
        iw, ih = reader.getSize()
        if not iw or not ih:
            return None

        w = float(max_width)
        h = w * (float(ih) / float(iw))
        return Image(BytesIO(png_bytes), width=w, height=h)
    except Exception as e:
        logger.warning("Could not embed logo in PDF (%s), using text fallback", e)
        return None


def _p(text):
    """Escape text for ReportLab Paragraph (XML-like markup)."""
    if text is None:
        return ""
    return xml_escape(str(text), entities={"'": "&apos;", '"': "&quot;"})


def _format_date_long(d):
    if d is None:
        return "-"
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.strftime("%d %B %Y")
    if isinstance(d, datetime):
        return timezone.localtime(d).strftime("%d %B %Y")
    return str(d)


def _format_datetime_long(dt):
    if dt is None:
        return "-"
    if isinstance(dt, datetime):
        return timezone.localtime(dt).strftime("%d %B %Y, %H:%M").strip()
    if hasattr(dt, "isoformat") and callable(dt.isoformat):
        raw = dt.isoformat()
        if isinstance(raw, str) and raw:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return timezone.localtime(parsed).strftime("%d %B %Y, %H:%M").strip()
            except ValueError:
                return raw
    return str(dt)


def _format_generated_at():
    return timezone.localtime(timezone.now()).strftime("%d %B %Y, %H:%M").strip()


def _build_period_label_human(billing_history):
    return coverage_period_label(
        billing_history.billing_date,
        billing_history.metadata or {},
    )


def _user_reference(metadata):
    ref = (metadata or {}).get("user_reference")
    if ref is None:
        return ""
    return str(ref).strip()


def _receipt_status_label(status):
    s = (status or "").strip().lower()
    if s == "paid":
        return "Paid — verified"
    return status or "-"


def _verified_by_label(billing_history):
    vb = getattr(billing_history, "verified_by", None)
    if vb is None:
        return "-"
    email = getattr(vb, "email", None) or ""
    name = (getattr(vb, "get_full_name", lambda: "")() or "").strip()
    if name and email:
        return f"{name} ({email})"
    return email or name or str(vb)


def _build_subscription_document_pdf(doc_title, billing_history, rows):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=doc_title,
    )
    content_width = A4[0] - doc.leftMargin - doc.rightMargin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="DocTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=4,
        textColor=_BRAND_DARK,
    )
    subtitle_style = ParagraphStyle(
        name="DocSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=_MUTED,
        spaceAfter=12,
    )
    footer_style = ParagraphStyle(
        name="DocFooter",
        parent=styles["Normal"],
        fontSize=8,
        textColor=_MUTED,
        leading=11,
    )

    elements = []

    bar = Table(
        [[""]],
        colWidths=[content_width],
        rowHeights=[4 * mm],
    )
    bar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _BRAND_BAR),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(bar)
    elements.append(Spacer(1, 10))

    logo_img = _make_logo_pdf_image(46 * mm)
    if logo_img is not None:
        elements.append(logo_img)
    else:
        elements.append(Paragraph(_p("Zentro"), title_style))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            _p("Official billing document — retain for your records."),
            subtitle_style,
        )
    )
    elements.append(Spacer(1, 8))

    heading = "INVOICE" if doc_title.lower() == "invoice" else "PAYMENT RECEIPT"
    elements.append(Paragraph(_p(heading), title_style))
    elements.append(
        Paragraph(
            _p(f"Document no. {billing_history.reference_number}"),
            subtitle_style,
        )
    )
    elements.append(Spacer(1, 6))

    table_rows = []
    for label, value in rows:
        table_rows.append(
            [
                Paragraph(f'<font color="{_MUTED_HEX}">{_p(label)}</font>', styles["Normal"]),
                Paragraph(f"<b>{_p(value)}</b>", styles["Normal"]),
            ]
        )

    detail = Table(
        table_rows,
        colWidths=[content_width * 0.38, content_width * 0.62],
        repeatRows=0,
    )
    detail.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, _TABLE_RULE),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, _TABLE_RULE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_TABLE_ALT_BG, colors.white]),
            ]
        )
    )
    elements.append(detail)
    elements.append(Spacer(1, 16))

    accent_line = Table([[""]], colWidths=[content_width], rowHeights=[1])
    accent_line.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _BRAND_ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(accent_line)
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            _p(
                "Thank you for your business. This document was generated by Zentro. "
                "If you have questions, reply to this email or contact support through the app."
            ),
            footer_style,
        )
    )
    elements.append(
        Paragraph(
            _p("zentroapp.app · Subscription billing"),
            footer_style,
        )
    )

    doc.build(elements)
    return buffer.getvalue()


def generate_invoice_pdf_bytes(billing_history):
    currency = billing_history.currency or "UGX"
    metadata = billing_history.metadata or {}
    rows = [
        ("Invoice number", billing_history.reference_number),
        ("Internal payment reference", billing_history.gateway_payment_id or "—"),
        ("Bill to", billing_history.company.name),
        ("Plan / product", billing_history.product),
        ("Amount due", _format_currency(billing_history.amount, currency)),
        ("Billing date", _format_date_long(billing_history.billing_date)),
        ("Coverage period", _build_period_label_human(billing_history)),
    ]
    ur = _user_reference(metadata)
    if ur:
        rows.append(("Customer transaction ID", ur))
    rows.append(("Generated", _format_generated_at()))
    return _build_subscription_document_pdf("Invoice", billing_history, rows)


def generate_receipt_pdf_bytes(billing_history):
    currency = billing_history.currency or "UGX"
    metadata = billing_history.metadata or {}
    rows = [
        ("Receipt number", billing_history.reference_number),
        ("Internal payment reference", billing_history.gateway_payment_id or "—"),
        ("Received from", billing_history.company.name),
        ("Plan / product", billing_history.product),
        ("Amount paid", _format_currency(billing_history.amount, currency)),
        ("Payment date", _format_date_long(billing_history.billing_date)),
        ("Status", _receipt_status_label(billing_history.status)),
        ("Verified on", _format_datetime_long(billing_history.verified_at)),
        ("Verified by", _verified_by_label(billing_history)),
    ]
    ur = _user_reference(metadata)
    if ur:
        rows.append(("Customer transaction ID", ur))
    rows.append(("Generated", _format_generated_at()))
    return _build_subscription_document_pdf("Payment receipt", billing_history, rows)


def _email_html_body(billing_history):
    company = html_escape(str(billing_history.company.name))
    ref = html_escape(str(billing_history.reference_number))
    pay_ref = html_escape(str(billing_history.gateway_payment_id or "—"))
    amount = html_escape(
        _format_currency(billing_history.amount, billing_history.currency or "UGX")
    )
    plan = html_escape(str(billing_history.product))
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f0f4f7;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f7;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,75,124,0.09);">
          <tr>
            <td style="height:6px;background:#006D68;"></td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px 28px;">
              <p style="margin:0;font-size:18px;font-weight:700;color:#004B7C;">Payment verified</p>
              <p style="margin:12px 0 0 0;font-size:14px;line-height:1.55;color:#5C6B7A;">
                Your mobile money subscription payment has been verified. Your invoice and receipt are attached as PDFs.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 28px 28px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #dde5ea;border-radius:8px;border-collapse:separate;">
                <tr>
                  <td style="padding:12px 16px;font-size:13px;color:#5C6B7A;border-bottom:1px solid #eef2f5;">Company</td>
                  <td style="padding:12px 16px;font-size:13px;color:#004B7C;font-weight:600;border-bottom:1px solid #eef2f5;">{company}</td>
                </tr>
                <tr>
                  <td style="padding:12px 16px;font-size:13px;color:#5C6B7A;border-bottom:1px solid #eef2f5;">Receipt no.</td>
                  <td style="padding:12px 16px;font-size:13px;color:#004B7C;font-weight:600;border-bottom:1px solid #eef2f5;">{ref}</td>
                </tr>
                <tr>
                  <td style="padding:12px 16px;font-size:13px;color:#5C6B7A;border-bottom:1px solid #eef2f5;">Payment reference</td>
                  <td style="padding:12px 16px;font-size:13px;color:#004B7C;font-weight:600;border-bottom:1px solid #eef2f5;">{pay_ref}</td>
                </tr>
                <tr>
                  <td style="padding:12px 16px;font-size:13px;color:#5C6B7A;border-bottom:1px solid #eef2f5;">Amount</td>
                  <td style="padding:12px 16px;font-size:13px;color:#004B7C;font-weight:600;border-bottom:1px solid #eef2f5;">{amount}</td>
                </tr>
                <tr>
                  <td style="padding:12px 16px;font-size:13px;color:#5C6B7A;">Plan</td>
                  <td style="padding:12px 16px;font-size:13px;color:#004B7C;font-weight:600;">{plan}</td>
                </tr>
              </table>
              <p style="margin:20px 0 0 0;font-size:12px;color:#5C6B7A;">
                Thank you for choosing Zentro.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_verified_mobile_money_subscription_receipt(billing_history):
    if _is_extra_users_payment(billing_history):
        return False
    if billing_history.status != "paid":
        return False

    recipient = _resolve_payer_email(billing_history)
    if not recipient:
        logger.warning(
            "Skipping receipt email for %s: no recipient",
            billing_history.reference_number,
        )
        return False

    subject = f"Your Zentro payment receipt ({billing_history.reference_number})"
    html = _email_html_body(billing_history)
    plain = (
        f"Your mobile-money subscription payment has been verified.\n"
        f"Company: {billing_history.company.name}\n"
        f"Receipt number: {billing_history.reference_number}\n"
        f"Payment reference: {billing_history.gateway_payment_id or '-'}\n"
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=plain,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@zentroapp.app"),
        to=[recipient],
    )
    message.attach_alternative(html, "text/html")
    message.attach(
        f"invoice-{billing_history.reference_number}.pdf",
        generate_invoice_pdf_bytes(billing_history),
        "application/pdf",
    )
    message.attach(
        f"receipt-{billing_history.reference_number}.pdf",
        generate_receipt_pdf_bytes(billing_history),
        "application/pdf",
    )
    message.send(fail_silently=False)
    logger.info(
        "Sent verification receipt email for %s to %s",
        billing_history.reference_number,
        recipient,
    )
    return True
