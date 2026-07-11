"""Business Central–style receipt report IDs (run a specific report by numeric id)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from receipt_templates.enums import ReceiptProcess, ReceiptType


@dataclass(frozen=True)
class ReceiptReportDefinition:
    report_id: int
    name: str
    caption: str
    receipt_type: str
    process: str
    description: str


class ReceiptReportId:
    """Numeric report ids — stable API contract (like BC Report objects)."""

    SALES_RECEIPT = 50000
    KITCHEN_ORDER = 50001
    BAR_ORDER = 50002
    GUEST_CHECK = 50003
    PREPAYMENT_RECEIPT = 50004
    PAYMENT_JOURNAL = 50005


RECEIPT_REPORTS: dict[int, ReceiptReportDefinition] = {
    ReceiptReportId.SALES_RECEIPT: ReceiptReportDefinition(
        report_id=ReceiptReportId.SALES_RECEIPT,
        name="SalesReceipt",
        caption="Sales Receipt",
        receipt_type=ReceiptType.SALE,
        process=ReceiptProcess.POS_SALE,
        description="Posted sales invoice / POS sale receipt",
    ),
    ReceiptReportId.KITCHEN_ORDER: ReceiptReportDefinition(
        report_id=ReceiptReportId.KITCHEN_ORDER,
        name="KitchenOrderTicket",
        caption="Kitchen Order Ticket",
        receipt_type=ReceiptType.KOT,
        process=ReceiptProcess.RESTAURANT_KOT,
        description="Kitchen order ticket (KOT) for restaurant checks",
    ),
    ReceiptReportId.BAR_ORDER: ReceiptReportDefinition(
        report_id=ReceiptReportId.BAR_ORDER,
        name="BarOrderTicket",
        caption="Bar Order Ticket",
        receipt_type=ReceiptType.BAR,
        process=ReceiptProcess.RESTAURANT_BAR,
        description="Bar order ticket for non-kitchen items",
    ),
    ReceiptReportId.GUEST_CHECK: ReceiptReportDefinition(
        report_id=ReceiptReportId.GUEST_CHECK,
        name="GuestCheck",
        caption="Guest Check",
        receipt_type=ReceiptType.INTERIM_BILL,
        process=ReceiptProcess.RESTAURANT_GUEST_CHECK,
        description="Interim bill / guest check before payment",
    ),
    ReceiptReportId.PREPAYMENT_RECEIPT: ReceiptReportDefinition(
        report_id=ReceiptReportId.PREPAYMENT_RECEIPT,
        name="PrepaymentReceipt",
        caption="Prepayment Receipt",
        receipt_type=ReceiptType.PREPAYMENT,
        process=ReceiptProcess.PREPAYMENT_POST,
        description="Customer prepayment receipt",
    ),
    ReceiptReportId.PAYMENT_JOURNAL: ReceiptReportDefinition(
        report_id=ReceiptReportId.PAYMENT_JOURNAL,
        name="PaymentJournalReceipt",
        caption="Payment Journal Receipt",
        receipt_type=ReceiptType.PAYMENT_JOURNAL,
        process=ReceiptProcess.PAYMENT_JOURNAL,
        description="Payment journal posting receipt",
    ),
}


def get_report_definition(report_id: int) -> Optional[ReceiptReportDefinition]:
    return RECEIPT_REPORTS.get(int(report_id))


def list_report_definitions() -> list[dict]:
    return [
        {
            "reportId": d.report_id,
            "name": d.name,
            "caption": d.caption,
            "receiptType": d.receipt_type,
            "process": d.process,
            "description": d.description,
        }
        for d in sorted(RECEIPT_REPORTS.values(), key=lambda x: x.report_id)
    ]
