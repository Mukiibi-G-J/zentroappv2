from enum import Enum


class InventoryType(Enum):
    Inventory = "Inventory"
    Service = "Service"
    NonInventory = "Non-Inventory"


class CostingMethod(Enum):
    FIFO = "FIFO"
    AVERAGE = "AVERAGE"
    SPECIFIC = "SPECIFIC"


class EntryType(Enum):
    Purchase = "Purchase"
    Sales = "Sales"
    PositiveAdjustment = "Positive Adjustment"
    NegativeAdjustment = "Negative Adjustment"
    DirectCost = "Direct Cost"
    Consumption = "Consumption"
    Output = "Output"


class DocumentType(Enum):
    default = ""
    Purchase = "Purchase"
    PurchaseReceipt = "Purchase Receipt"
    Adjustment = "Adjustment"
    Invoice = "Invoice"
    Payment = "Payment"
    Sales = "Sales"


class ReplenishmentSystem(Enum):
    """Replenishment System enum for Item"""
    Purchase = "Purchase"
    ProdOrder = "Prod. Order"
    Transfer = "Transfer"
    Assembly = "Assembly"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class ManufacturingPolicy(Enum):
    """Manufacturing Policy enum for Item"""
    MakeToStock = "Make-to-Stock"
    MakeToOrder = "Make-to-Order"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FlushingMethod(Enum):
    """Flushing Method enum for Item"""
    Manual = "Manual"
    Forward = "Forward"
    Backward = "Backward"
    PickForward = "Pick + Forward"
    PickBackward = "Pick + Backward"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]
