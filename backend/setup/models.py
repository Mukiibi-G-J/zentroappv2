from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

from financials.enums import BalacingAccountType
from setup.enums import (
    EmailSetupStatus,
    EmailCategory,
    UploadTemplateChoices,
    JournalType,
)
from utils.utils import BaseModel, SingletonSetupModel


class EmailSetup(models.Model):
    from_email = models.EmailField(unique=True)
    subject = models.CharField(max_length=255)
    message_template = models.TextField()

    # New fields for SMTP configuration
    email_host = models.CharField(max_length=255, default="smtp.gmail.com")
    email_host_user = models.EmailField(unique=True)
    email_host_password = models.CharField(max_length=255)
    email_port = models.IntegerField(default=587)
    email_use_tls = models.BooleanField(default=True)
    status = models.CharField(
        max_length=255,
        choices=[(status.value, status.value) for status in EmailSetupStatus],
    )
    email_category = models.CharField(
        max_length=255,
        choices=[(category.value, category.value) for category in EmailCategory],
    )

    def save(self, *args, **kwargs):
        # category should appear only once
        if (
            EmailSetup.objects.filter(email_category=self.email_category)
            .exclude(id=self.id)
            .exists()
        ):
            raise ValueError(f"Only one {self.email_category} email setup is allowed")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Email Setup: {self.subject}"


class SiteSettings(BaseModel):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="site_settings/", null=True, blank=True)


class NoSeries(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=255, unique=True)

    def _first_line(self):
        return self.noserieslines_set.order_by('start_number').first()

    @property
    def starting_no(self):
        line = self._first_line()
        return line.start_number if line else None

    @property
    def ending_no(self):
        line = self._first_line()
        return line.end_number if line else None

    @property
    def last_date_used(self):
        line = self._first_line()
        return line.last_used_date if line else None

    @property
    def last_no_used(self):
        line = self._first_line()
        return line.last_used_number if line else None

    def __str__(self):
        return f"{self.code} - {self.description}"

    class Meta:
        verbose_name_plural = "No Series"
        verbose_name = "No Series"
        ordering = ["-created_at"]


class NoSeriesLines(BaseModel):
    no_series = models.ForeignKey(NoSeries, on_delete=models.CASCADE)
    start_number = models.CharField(max_length=20)
    end_number = models.CharField(max_length=20, null=True, blank=True)
    last_used_number = models.CharField(max_length=20, null=True, blank=True)
    last_used_date = models.DateField(null=True, blank=True)
    increment_by = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.no_series.code} - {self.start_number} - {self.end_number} - {self.last_used_number} - {self.last_used_date}"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def has_no_spaces(self, text):
        return not any(char.isspace() for char in text)

    def clean(self):
        if self.start_number:
            print(self.start_number)
            if not self.has_no_spaces(self.start_number):
                raise ValidationError(
                    {
                        "start_number": "Start number cannot contain spaces",
                    }
                )
            if not re.match(r"^\D*\d+$", self.start_number):
                raise ValidationError(
                    {
                        "start_number": "Start number must end with a number and contain no invalid characters"
                    }
                )

    class Meta:
        verbose_name_plural = "No Series Lines"
        verbose_name = "No Series Line"
        ordering = ["-created_at"]
        unique_together = ("no_series", "start_number")


class InventorySetup(SingletonSetupModel):
    item_no_series = models.ForeignKey(
        NoSeries, on_delete=models.CASCADE, verbose_name="Item No's."
    )
    item_journal_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Item Journal No's.",
        help_text="Number series for item journals",
        related_name="inventory_setups_item_journal",
    )
    show_adjustment_history_before_after = models.BooleanField(
        default=True,
        verbose_name="Show Adjustment History Before/After",
        help_text="Display 'Adjusted from X to Y' in Inventory Adjustment History",
    )

    def __str__(self):
        return f"Inventory Setup: {self.item_no_series}"

    def clean(self):
        if self.item_no_series:
            if not NoSeriesLines.objects.filter(no_series=self.item_no_series).exists():
                raise ValidationError(
                    {
                        "item_no_series": "Start number for item no's. is not set",
                    }
                )
            else:
                if (
                    not NoSeriesLines.objects.filter(no_series=self.item_no_series)
                    .first()
                    .start_number
                ):
                    raise ValidationError(
                        {
                            "item_no_series": "Start number for item no's. is not set",
                        }
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Inventory Setup"
        verbose_name_plural = "Inventory Setup"


class JournalSetup(BaseModel):
    journal_no_series = models.ForeignKey(
        NoSeries, on_delete=models.CASCADE, verbose_name="Journal No's."
    )
    journal_type = models.CharField(
        max_length=255,
        choices=[(tag.value, tag.value) for tag in JournalType],
        default=JournalType.ITEM.value,
    )

    class Meta:
        verbose_name_plural = "Journal Setup"
        verbose_name = "Journal Setup"


class BankAccountSetup(BaseModel):
    bank_account_no_series = models.ForeignKey(
        NoSeries, on_delete=models.CASCADE, verbose_name="Bank Account No's."
    )

    def __str__(self):
        return f"Bank Account Setup: {self.bank_account_no_series}"

    def clean(self):
        if self.bank_account_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.bank_account_no_series
            ).exists():
                raise ValidationError(
                    {
                        "bank_account_no_series": "Start number for bank account no's. is not set",
                    }
                )
            else:
                if (
                    not NoSeriesLines.objects.filter(
                        no_series=self.bank_account_no_series
                    )
                    .first()
                    .start_number
                ):
                    raise ValidationError(
                        {
                            "bank_account_no_series": "Start number for bank account no's. is not set",
                        }
                    )

    class Meta:
        verbose_name_plural = "Bank Account Setup"
        verbose_name = "Bank Account Setup"


class ResourceSetup(BaseModel):
    """
    Setup model for Resources.

    Used to store the number series that will be used to generate
    Resource codes from the No Series pages.
    """

    resource_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        verbose_name="Resource No's.",
        help_text="Number series for Resources",
    )

    def __str__(self):
        return f"Resource Setup: {self.resource_no_series}"

    def clean(self):
        if self.resource_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.resource_no_series
            ).exists():
                raise ValidationError(
                    {
                        "resource_no_series": "Start number for Resource no's. is not set",
                    }
                )
            else:
                line = NoSeriesLines.objects.filter(
                    no_series=self.resource_no_series
                ).first()
                if not line or not line.start_number:
                    raise ValidationError(
                        {
                            "resource_no_series": "Start number for Resource no's. is not set",
                        }
                    )

    class Meta:
        verbose_name_plural = "Resource Setup"
        verbose_name = "Resource Setup"


class CompanyInformation(SingletonSetupModel):
    """Tenant-side company profile card; syncs editable fields to the public Company tenant."""

    name = models.CharField(
        max_length=100,
        verbose_name='Company Name',
        help_text='Legal company name (read-only)',
    )
    display_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Display Name',
    )
    logo = models.ImageField(
        upload_to='company_logos/',
        null=True,
        blank=True,
    )
    address = models.CharField(max_length=255, blank=True, default='')
    phone = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    website = models.URLField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    tin = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        verbose_name = 'Company Information'
        verbose_name_plural = 'Company Information'

    def __str__(self):
        return self.display_name or self.name

    @classmethod
    def _resolve_public_company(cls):
        from django.db import connection
        from django_tenants.utils import schema_context
        from company.models import Company

        tenant = getattr(connection, 'tenant', None)
        if tenant is not None and hasattr(tenant, 'name'):
            return tenant

        schema_name = getattr(connection, 'schema_name', None)
        if not schema_name or schema_name == 'public':
            return None

        with schema_context('public'):
            return Company.objects.filter(schema_name=schema_name).first()

    @classmethod
    def sync_from_public_company(cls):
        company = cls._resolve_public_company()
        if company is None:
            return None

        obj = cls.objects.first()
        if obj is None:
            obj = cls()

        obj.name = company.name
        obj.display_name = company.display_name or company.name
        obj.address = company.address or ''
        obj.phone = company.phone or ''
        obj.email = company.email or ''
        obj.website = company.website or None
        obj.city = company.city
        obj.country = company.country
        obj.tin = company.tin or ''
        if company.logo:
            obj.logo = company.logo
        obj.save()
        return obj

    def sync_to_public_company(self):
        from django_tenants.utils import schema_context

        company = self._resolve_public_company()
        if company is None:
            return

        company_id = company.pk
        with schema_context('public'):
            from company.models import Company

            public_company = Company.objects.filter(pk=company_id).first()
            if public_company is None:
                return

            public_company.display_name = self.display_name or public_company.name
            public_company.address = self.address or ''
            public_company.phone = self.phone or ''
            public_company.email = self.email or ''
            public_company.website = self.website or None
            public_company.city = self.city
            public_company.country = self.country
            public_company.tin = self.tin or public_company.tin
            if self.logo:
                public_company.logo = self.logo
            public_company.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_to_public_company()


class CompanySubscription(SingletonSetupModel):
    """Read-only tenant mirror of the public Subscription for the Company card billing action."""

    plan = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=20, blank=True, default='')
    billing_cycle = models.CharField(max_length=20, blank=True, default='')
    is_active = models.BooleanField(default=False)
    in_grace_period = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    days_remaining = models.IntegerField(default=0)
    grace_days_remaining = models.IntegerField(default=0)
    period_end_date = models.DateField(null=True, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    subscription_end_date = models.DateField(null=True, blank=True)
    access_lock_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Company Subscription'
        verbose_name_plural = 'Company Subscription'

    def __str__(self):
        return self.plan or 'Subscription'

    @classmethod
    def sync_from_public(cls):
        from setup.company_sync import sync_company_subscription

        return sync_company_subscription()


class CompanyBillingHistory(BaseModel):
    """Read-only mirror of public BillingHistory rows for list pages."""

    public_id = models.IntegerField(unique=True, db_index=True)
    reference_number = models.CharField(max_length=10)
    product = models.CharField(max_length=100)
    status = models.CharField(max_length=30)
    billing_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')

    class Meta:
        verbose_name = 'Billing History'
        verbose_name_plural = 'Billing History'
        ordering = ['-billing_date', '-id']

    def __str__(self):
        return self.reference_number


class CompanyPaymentMethod(BaseModel):
    """Read-only mirror of public PaymentMethod rows for list pages."""

    public_id = models.IntegerField(unique=True, db_index=True)
    method_type = models.CharField(max_length=50)
    holder_name = models.CharField(max_length=100)
    last_four_digits = models.CharField(max_length=4, blank=True, default='')
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_primary', 'holder_name']

    def __str__(self):
        suffix = f' •••• {self.last_four_digits}' if self.last_four_digits else ''
        return f'{self.holder_name}{suffix}'


class ManufacturingSetup(SingletonSetupModel):
    manufacturing_enabled = models.BooleanField(
        default=False,
        verbose_name="Manufacturing Enabled",
        help_text="When enabled, items will show Production BOM section for defining bill of materials.",
    )
    bom_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        verbose_name="BOM No's.",
        related_name="bom_manufacturing_setups",
    )
    production_order_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Production Order No's.",
        help_text="Number series for Production Orders",
        related_name="production_order_manufacturing_setups",
    )
    work_center_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Work Center No's.",
        help_text="Number series for Work Centers",
        related_name="work_center_manufacturing_setups",
    )
    machine_center_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Machine Center No's.",
        help_text="Number series for Machine Centers",
        related_name="machine_center_manufacturing_setups",
    )
    routing_no_series = models.ForeignKey(
        NoSeries,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Routing No's.",
        help_text="Number series for Routings",
        related_name="routing_manufacturing_setups",
    )

    def __str__(self):
        return f"Manufacturing Setup: {self.bom_no_series}"

    def clean(self):
        if self.bom_no_series:
            if not NoSeriesLines.objects.filter(no_series=self.bom_no_series).exists():
                raise ValidationError(
                    {
                        "bom_no_series": "Start number for BOM no's. is not set",
                    }
                )
            else:
                if (
                    not NoSeriesLines.objects.filter(no_series=self.bom_no_series)
                    .first()
                    .start_number
                ):
                    raise ValidationError(
                        {
                            "bom_no_series": "Start number for BOM no's. is not set",
                        }
                    )

        if self.production_order_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.production_order_no_series
            ).exists():
                raise ValidationError(
                    {
                        "production_order_no_series": "Start number for Production Order no's. is not set",
                    }
                )
            else:
                no_series_line = NoSeriesLines.objects.filter(
                    no_series=self.production_order_no_series
                ).first()
                if not no_series_line or not no_series_line.start_number:
                    raise ValidationError(
                        {
                            "production_order_no_series": "Start number for Production Order no's. is not set",
                        }
                    )

        if self.work_center_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.work_center_no_series
            ).exists():
                raise ValidationError(
                    {
                        "work_center_no_series": "Start number for Work Center no's. is not set",
                    }
                )
            else:
                no_series_line = NoSeriesLines.objects.filter(
                    no_series=self.work_center_no_series
                ).first()
                if not no_series_line or not no_series_line.start_number:
                    raise ValidationError(
                        {
                            "work_center_no_series": "Start number for Work Center no's. is not set",
                        }
                    )

        if self.machine_center_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.machine_center_no_series
            ).exists():
                raise ValidationError(
                    {
                        "machine_center_no_series": "Start number for Machine Center no's. is not set",
                    }
                )
            else:
                no_series_line = NoSeriesLines.objects.filter(
                    no_series=self.machine_center_no_series
                ).first()
                if not no_series_line or not no_series_line.start_number:
                    raise ValidationError(
                        {
                            "machine_center_no_series": "Start number for Machine Center no's. is not set",
                        }
                    )

        if self.routing_no_series:
            if not NoSeriesLines.objects.filter(
                no_series=self.routing_no_series
            ).exists():
                raise ValidationError(
                    {
                        "routing_no_series": "Start number for Routing no's. is not set",
                    }
                )
            else:
                no_series_line = NoSeriesLines.objects.filter(
                    no_series=self.routing_no_series
                ).first()
                if not no_series_line or not no_series_line.start_number:
                    raise ValidationError(
                        {
                            "routing_no_series": "Start number for Routing no's. is not set",
                        }
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Manufacturing Setup"
        verbose_name = "Manufacturing Setup"


class UploadTemplates(BaseModel):
    name = models.CharField(
        max_length=255,
        choices=[(choice.value, choice.value) for choice in UploadTemplateChoices],
    )
    file = models.FileField(upload_to="upload_templates/")

    def __str__(self):
        return f"Upload Template: {self.name}"


class SeedManager(BaseModel):
    """
    Singleton model for managing seed commands.
    This model is used as a placeholder in admin to provide seed command actions.
    Only one instance should exist (enforced by save method).
    """

    name = models.CharField(
        max_length=255,
        default="Seed Manager",
        help_text="Name for the seed manager instance",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of seed operations",
    )

    class Meta:
        verbose_name = "Seed Manager"
        verbose_name_plural = "Seed Manager"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SeedManager.objects.exists():
            raise ValidationError("Only one SeedManager instance is allowed")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
