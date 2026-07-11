import enum


class CapacityUnitOfMeasureType(enum.Enum):
    """Capacity Unit of Measure Type enum"""
    MILLISECONDS = "Milliseconds"
    HUNDRED_PER_HOUR = "100/Hour"
    MINUTES = "Minutes"
    HOURS = "Hours"
    DAYS = "Days"
    SECONDS = "Seconds"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class DayOfWeek(enum.Enum):
    """Day of Week enum for Shop Calendar"""
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class UnitCostCalculation(enum.Enum):
    """Unit Cost Calculation enum for Work Center"""
    UNITS = "Units"
    TIME = "Time"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]

