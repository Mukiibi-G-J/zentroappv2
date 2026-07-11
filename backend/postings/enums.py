import enum

class DimensionType(enum.Enum):
    Standard = "Standard"
    Custom = "Custom"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]
