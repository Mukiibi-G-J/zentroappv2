"""Shared receipt template seeding (used by seed_receipt_templates and seed_restaurant_module)."""

from __future__ import annotations

from receipt_templates.defaults import DEFAULT_ASSIGNMENTS, SYSTEM_TEMPLATES
from receipt_templates.models import ReceiptTemplate, ReceiptTemplateAssignment


def seed_receipt_templates(
    stdout,
    style,
    *,
    clear_assignments: bool = False,
) -> tuple[int, int]:
    """
    Seed system receipt templates and default assignments in the **current** DB schema.

    Returns (template_count, new_assignment_count).
    """
    if clear_assignments:
        ReceiptTemplateAssignment.objects.filter(branch__isnull=True).delete()

    code_to_template: dict[str, ReceiptTemplate] = {}
    for spec in SYSTEM_TEMPLATES:
        tpl, created = ReceiptTemplate.objects.update_or_create(
            code=spec["code"],
            defaults={
                "name": spec["name"],
                "receipt_type": spec["receipt_type"],
                "layout_preset": spec["layout_preset"],
                "paper_profile": spec["paper_profile"],
                "sections": spec["sections"],
                "is_system": True,
                "is_active": True,
            },
        )
        code_to_template[spec["code"]] = tpl
        action = "Created" if created else "Updated"
        stdout.write(f"  {action} receipt template: {tpl.code}")

    created_asn = 0
    for (
        template_code,
        device_type,
        printer_type,
        process,
        priority,
    ) in DEFAULT_ASSIGNMENTS:
        tpl = code_to_template.get(template_code)
        if not tpl:
            continue
        _, created = ReceiptTemplateAssignment.objects.get_or_create(
            template=tpl,
            device_type=device_type,
            printer_type=printer_type,
            process=process,
            branch=None,
            defaults={"priority": priority},
        )
        if created:
            created_asn += 1

    stdout.write(
        style.SUCCESS(
            f"Receipt templates: {len(code_to_template)} template(s), "
            f"{created_asn} new assignment(s)"
        )
    )
    return len(code_to_template), created_asn
