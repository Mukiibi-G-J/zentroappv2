# Data Files

This directory contains JSON fixture files for loading initial data into the application.

## Available Data Files

- `pricing_plans.json` - Subscription pricing plans
- `business_categories.json` - Business categories
- `business_objectives.json` - Business objectives
- `default_no_series.json` - Default number series
- `smtp_setup.json` - SMTP configuration

## Loading Pricing Plans

To load the pricing plans data, use the custom management command:

```bash
# Load pricing plans (will add to existing data)
python manage.py load_pricing_plans

# Clear existing pricing plans and load new ones
python manage.py load_pricing_plans --clear

# Load from a specific file
python manage.py load_pricing_plans --file path/to/custom_pricing.json
```

## Pricing Plans Included

1. **Standard Plan** - UGX 30,000/month

   - Full Inventory Management
   - Unlimited Products
   - Basic Reports
   - Customer Management
   - 24/7 Support
   - Mobile App Access

2. **Multi-Branch Plan** - UGX 50,000/month

   - Everything in Standard Plan
   - Multi-Branch Support (per branch)

3. **Premium Plan with EFRIS** - UGX 80,000/month
   - Everything in Multi-Branch Plan
   - EFRIS Integration
   - Advanced Analytics
   - Priority Support
   - Custom Reports
   - API Access

## Using Django's loaddata Command

You can also use Django's built-in `loaddata` command:

```bash
# Load all data files
python manage.py loaddata data/*.json

# Load specific file
python manage.py loaddata data/pricing_plans.json
```

## Annual Pricing

All plans also include annual pricing with discounts:

- Standard Plan: UGX 288,000/year (20% discount)
- Multi-Branch Plan: UGX 480,000/year (20% discount)
- Premium Plan with EFRIS: UGX 768,000/year (20% discount)
