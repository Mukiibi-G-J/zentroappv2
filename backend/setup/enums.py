from enum import Enum


class EmailSetupStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EmailCategory(Enum):
    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"
    INVITATION = "invitation"
    OTHER = "other"


class UploadTemplateChoices(Enum):
    ITEMS = "items"
    SALES = "sales"
    PURCHASES = "purchases"
    INVENTORY = "inventory"


class JournalType(Enum):
    ITEM = "item"
    PAYMENT = "payment"
    EXPENSE = "expense"
    LOAN = "loan"
