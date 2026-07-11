"""
Add included_modules to Pricing model and module_overrides to Company model.
Also backfill included_modules for existing Pricing records and recompute
enabled_modules for existing companies.
"""

from django.db import migrations, models


STARTER_MODULES = [
    "sales", "inventory", "purchases", "customers", "expenses",
    "reports", "financials", "payments", "prepayments", "bank_accounts",
    "user_management",
]

BUSINESS_MODULES = STARTER_MODULES + [
    "item_tracking", "stock_taking", "manufacturing", "loans", "resources",
]

PRO_MODULES = BUSINESS_MODULES + ["efris"]

PLAN_TO_MODULES = {
    "Starter": STARTER_MODULES,
    "Business": BUSINESS_MODULES,
    "Pro": PRO_MODULES,
}


def backfill_pricing_modules(apps, schema_editor):
    """Populate included_modules on existing Pricing records."""
    Pricing = apps.get_model("company", "Pricing")
    for pricing in Pricing.objects.all():
        modules = PLAN_TO_MODULES.get(pricing.name, STARTER_MODULES)
        pricing.included_modules = modules
        pricing.save(update_fields=["included_modules"])


def recompute_company_modules(apps, schema_editor):
    """Set enabled_modules for every company based on their subscription plan."""
    Company = apps.get_model("company", "Company")
    Subscription = apps.get_model("company", "Subscription")
    Pricing = apps.get_model("company", "Pricing")

    for company in Company.objects.all():
        try:
            sub = Subscription.objects.get(company=company)
        except Subscription.DoesNotExist:
            continue

        pricing = Pricing.objects.filter(name=sub.plan, is_active=True).first()
        plan_modules = pricing.included_modules if pricing and pricing.included_modules else []
        overrides = company.module_overrides or []

        current = set(company.enabled_modules or [])
        plan_set = set(plan_modules)

        extra = list(current - plan_set)
        if extra:
            company.module_overrides = list(set(overrides + extra))

        combined = list(set(plan_modules + (company.module_overrides or [])))
        company.enabled_modules = combined
        company.save(update_fields=["enabled_modules", "module_overrides"])


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0010_billing_expiry_reminder_add_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricing",
            name="included_modules",
            field=models.JSONField(
                default=list,
                help_text="Module identifiers included in this plan (e.g., ['sales', 'inventory'])",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="module_overrides",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Manually enabled modules beyond the subscription plan (waivers/deals)",
            ),
        ),
        migrations.RunPython(
            backfill_pricing_modules,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            recompute_company_modules,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
