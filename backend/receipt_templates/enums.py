from django.db import models


class ReceiptType(models.TextChoices):
    SALE = "sale", "Sale"
    PREPAYMENT = "prepayment", "Prepayment"
    KOT = "kot", "Kitchen order"
    BAR = "bar", "Bar order"
    INTERIM_BILL = "interim_bill", "Guest check / interim bill"
    PAYMENT_JOURNAL = "payment_journal", "Payment journal"


class LayoutPreset(models.TextChoices):
    COMPACT = "compact", "Compact"
    STANDARD = "standard", "Standard"
    DETAILED = "detailed", "Detailed"


class EditorMode(models.TextChoices):
    VISUAL = "visual", "Visual (sections)"
    FORMAT_STRING = "format_string", "Format string"


class DeviceType(models.TextChoices):
    ANY = "any", "Any device"
    WEB = "web", "Web"
    MOBILE = "mobile", "Mobile"
    DESKTOP = "desktop", "Desktop"


class PrinterType(models.TextChoices):
    ANY = "any", "Any printer"
    BROWSER = "browser", "Browser print"
    SERIAL = "serial", "Serial / ESC-POS"
    SUNMI = "sunmi", "Sunmi built-in"
    BLUETOOTH = "bluetooth", "Bluetooth"
    USB = "usb", "USB"
    DESKTOP_SILENT = "desktop_silent", "Desktop silent print"


class ReceiptProcess(models.TextChoices):
    ANY = "any", "Any process"
    POS_SALE = "pos_sale", "POS sale"
    SALES_HISTORY_REPRINT = "sales_history_reprint", "Sales history reprint"
    PREPAYMENT_POST = "prepayment_post", "Prepayment post"
    RESTAURANT_SETTLE = "restaurant_settle", "Restaurant settle"
    RESTAURANT_KOT = "restaurant_kot", "Restaurant KOT"
    RESTAURANT_BAR = "restaurant_bar", "Restaurant bar"
    RESTAURANT_GUEST_CHECK = "restaurant_guest_check", "Restaurant guest check"
    PAYMENT_JOURNAL = "payment_journal", "Payment journal"
