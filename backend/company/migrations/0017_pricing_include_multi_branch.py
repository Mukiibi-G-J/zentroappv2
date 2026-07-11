"""
Business / Pro tiers advertise multi-branch ("Up to 3" / unlimited) but
included_modules omitted multi_branch, so overrides were never pruned after upgrade.

Append multi_branch to those Pricing rows and prune company module_overrides
without calling compute_enabled_modules() (that touches tenant-only tables
during public-schema migration).
"""
from django.db import migrations


def forwards(apps, schema_editor):
    from django.core.exceptions import ObjectDoesNotExist

    from company.models import Company, Pricing

    mapping = Company.PLAN_NAME_TO_PRICING

    for name in ("Business", "Pro"):
        for p in Pricing.objects.filter(name=name):
            mods = list(p.included_modules or [])
            if "multi_branch" in mods:
                continue
            mods.append("multi_branch")
            p.included_modules = mods
            p.save(update_fields=["included_modules"])

    for company in Company.objects.iterator():
        try:
            sub = company.subscription
        except ObjectDoesNotExist:
            continue
        plan_key = sub.plan or ""
        pricing_name = mapping.get(plan_key, plan_key)
        if not pricing_name and sub.status in ("trial", "active"):
            pricing_name = "Starter"
        if pricing_name not in ("Business", "Pro"):
            continue
        pricing = Pricing.objects.filter(name=pricing_name).first()
        if not pricing:
            continue
        plan_modules = list(pricing.included_modules or [])
        plan_set = set(plan_modules)
        overrides = list(company.module_overrides or [])
        pruned = [m for m in overrides if m not in plan_set]
        combined = list(set(plan_modules + pruned))
        if pruned == overrides and set(company.enabled_modules or []) == set(combined):
            continue
        company.module_overrides = pruned
        company.enabled_modules = combined
        company.save(update_fields=["module_overrides", "enabled_modules"])


def backwards(apps, schema_editor):
    from company.models import Pricing

    for name in ("Business", "Pro"):
        for p in Pricing.objects.filter(name=name):
            mods = [m for m in (p.included_modules or []) if m != "multi_branch"]
            p.included_modules = mods
            p.save(update_fields=["included_modules"])


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0016_company_subscription_grace_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
