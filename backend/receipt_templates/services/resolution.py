from __future__ import annotations

from typing import Any, Optional

from receipt_templates.enums import DeviceType, PrinterType, ReceiptProcess, ReceiptType
from receipt_templates.models import ReceiptTemplate, ReceiptTemplateAssignment


def _score_assignment(
    assignment: ReceiptTemplateAssignment,
    device_type: str,
    printer_type: str,
    process: str,
    branch_id: Optional[int],
) -> int:
    score = assignment.priority * 1000
    if assignment.device_type != DeviceType.ANY:
        if assignment.device_type == device_type:
            score += 100
        else:
            return -1
    else:
        score += 10

    if assignment.printer_type != PrinterType.ANY:
        if assignment.printer_type == printer_type:
            score += 100
        else:
            return -1
    else:
        score += 10

    if assignment.process != ReceiptProcess.ANY:
        if assignment.process == process:
            score += 100
        else:
            return -1
    else:
        score += 10

    if assignment.branch_id:
        if branch_id and assignment.branch_id == branch_id:
            score += 200
        else:
            return -1
    else:
        score += 5

    return score


def resolve_receipt_template(
    *,
    receipt_type: str,
    device_type: str = DeviceType.ANY,
    printer_type: str = PrinterType.ANY,
    process: str = ReceiptProcess.ANY,
    branch_id: Optional[int] = None,
) -> Optional[ReceiptTemplate]:
    """Pick best matching active template for the given print context."""
    if receipt_type not in dict(ReceiptType.choices):
        receipt_type = ReceiptType.SALE

    assignments = (
        ReceiptTemplateAssignment.objects.filter(
            template__receipt_type=receipt_type,
            template__is_active=True,
        )
        .select_related("template")
        .order_by("-priority", "-created_at")
    )

    best: Optional[ReceiptTemplateAssignment] = None
    best_score = -1

    for asn in assignments:
        s = _score_assignment(asn, device_type, printer_type, process, branch_id)
        if s > best_score:
            best_score = s
            best = asn

    if best:
        return best.template

    # Fallback: first active system template for receipt type
    return (
        ReceiptTemplate.objects.filter(
            receipt_type=receipt_type,
            is_active=True,
        )
        .order_by("-is_system", "code")
        .first()
    )


def template_to_dict(template: ReceiptTemplate) -> dict[str, Any]:
    sections = sorted(
        template.sections or [],
        key=lambda s: int(s.get("order", 0)),
    )
    return {
        "id": template.id,
        "code": template.code,
        "name": template.name,
        "receiptType": template.receipt_type,
        "layoutPreset": template.layout_preset,
        "paperProfile": template.paper_profile or {},
        "sections": sections,
        "editorMode": template.editor_mode,
        "formatString": template.format_string or "",
        "isSystem": template.is_system,
        "isActive": template.is_active,
    }
