from django.db import models
from utils.utils import BaseModel
from postings import enums


# Remove this import to break the circular dependency
# from financials.models import G_LAccount

# Create your models here.


class GeneralProductPostingGroup(BaseModel):
    code = models.CharField(max_length=255, unique=True, primary_key=True)
    description = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}"


class VATProductPostingGroup(BaseModel):
    code = models.CharField(max_length=255, unique=True, primary_key=True)
    description = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}"


class VATBusinessPostingGroup(BaseModel):
    code = models.CharField(max_length=255, unique=True, primary_key=True)
    description = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}"


class GeneralBusinessPostingGroup(BaseModel):
    code = models.CharField(max_length=255, unique=True, primary_key=True)
    description = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}"


class GeneralPostingSetup(BaseModel):
    general_product_posting_group = models.ForeignKey(
        GeneralProductPostingGroup,
        on_delete=models.CASCADE,
        related_name="general_product_posting_group",
        blank=True,
        null=True,
        to_field="code",
    )
    general_business_posting_group = models.ForeignKey(
        GeneralBusinessPostingGroup,
        on_delete=models.CASCADE,
        related_name="general_business_posting_group",
        blank=True,
        null=True,
        to_field="code",
    )

    # Use string reference instead of direct model import
    sales_account = models.ForeignKey(
        "financials.G_LAccount",  # Changed to string reference
        verbose_name="Sales Account",
        on_delete=models.CASCADE,
        related_name="sales_account_postings",
        blank=True,
        null=True,
        to_field="no",
    )
    purchase_account = models.ForeignKey(
        "financials.G_LAccount",  # Changed to string reference
        verbose_name="Purchase Account",
        on_delete=models.CASCADE,
        related_name="purchase_account_postings",
        blank=True,
        null=True,
        to_field="no",
    )

    cogs_account = models.ForeignKey(
        "financials.G_LAccount",  # Changed to string reference
        verbose_name="Cogs Account",
        on_delete=models.CASCADE,
        related_name="cogs_account_postings",
        blank=True,
        null=True,
        to_field="no",
    )
    inventory_adjustment_account = models.ForeignKey(
        "financials.G_LAccount",  # Changed to string reference
        verbose_name="Inventory Adjustment Account",
        on_delete=models.CASCADE,
        related_name="inventory_adjustment_postings",
        blank=True,
        null=True,
        to_field="no",
    )
    direct_cost_applied_account = models.ForeignKey(
        "financials.G_LAccount",  # Changed to string reference
        verbose_name="Direct Cost Applied Account",
        on_delete=models.CASCADE,
        related_name="direct_cost_applied_postings",
        blank=True,
        null=True,
        to_field="no",
    )
    prepayment_account = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name="Prepayment Account",
        on_delete=models.CASCADE,
        related_name="prepayment_postings",
        blank=True,
        null=True,
        to_field="no",
    )
    sales_line_discount_account = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name="Sales Line Discount Account",
        on_delete=models.CASCADE,
        related_name="sales_line_discount_postings",
        blank=True,
        null=True,
        to_field="no",
    )

    def save(self, *args, **kwargs):
        if (
            not self.general_product_posting_group
            and not self.general_business_posting_group
        ):
            raise ValueError("Business or Product Posting Group is required")
        super().save(*args, **kwargs)


class VATPostingSetup(BaseModel):
    """BC-style VAT Posting Setup: combines VAT Business + Product groups with rate and G/L accounts."""

    VAT_CALCULATION_TYPES = [
        ("Normal", "Normal"),
        ("Full VAT", "Full VAT"),
        ("Reverse Charge", "Reverse Charge"),
    ]

    vat_business_posting_group = models.ForeignKey(
        VATBusinessPostingGroup,
        on_delete=models.CASCADE,
        related_name="vat_posting_setups",
        verbose_name="VAT Bus. Posting Group",
        to_field="code",
    )
    vat_product_posting_group = models.ForeignKey(
        VATProductPostingGroup,
        on_delete=models.CASCADE,
        related_name="vat_posting_setups",
        verbose_name="VAT Prod. Posting Group",
        to_field="code",
    )
    vat_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="VAT %",
        help_text="VAT percentage, e.g. 18.00",
    )
    vat_calculation_type = models.CharField(
        max_length=20,
        choices=VAT_CALCULATION_TYPES,
        default="Normal",
        verbose_name="VAT Calculation Type",
    )
    sales_vat_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.PROTECT,
        related_name="sales_vat_postings",
        verbose_name="VAT Sales Account",
        blank=True,
        null=True,
        to_field="no",
        help_text="G/L account for sales VAT (output VAT).",
    )
    purchase_vat_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.PROTECT,
        related_name="purchase_vat_postings",
        verbose_name="VAT Purchase Account",
        blank=True,
        null=True,
        to_field="no",
        help_text="G/L account for purchase VAT (input VAT).",
    )
    vat_identifier = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="VAT Identifier",
        help_text="For grouping/reporting, e.g. VAT18.",
    )

    class Meta:
        unique_together = (("vat_business_posting_group", "vat_product_posting_group"),)
        verbose_name = "VAT Posting Setup"
        verbose_name_plural = "VAT Posting Setups"

    def __str__(self):
        return f"{self.vat_business_posting_group_id} + {self.vat_product_posting_group_id} ({self.vat_percent}%)"


class InventoryPostingGroup(BaseModel):
    code = models.CharField(max_length=255, unique=True, primary_key=True)
    description = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}"


class InventoryPostingSetup(BaseModel):
    location = models.ForeignKey(
        "items.Location",
        on_delete=models.CASCADE,
        verbose_name="Location",
        to_field="code",
        blank=True,
        null=True,
    )
    inventory_posting_group = models.ForeignKey(
        InventoryPostingGroup,
        on_delete=models.CASCADE,
        verbose_name="Inventory Posting Group",
        to_field="code",
    )
    inventory_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.CASCADE,
        verbose_name="Inventory Account",
        to_field="no",
    )
    wip_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.CASCADE,
        verbose_name="WIP Account",
        to_field="no",
        blank=True,
        null=True,
        related_name="wip_account_setups",
    )
