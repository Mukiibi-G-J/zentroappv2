from django import forms

from authentication.models import RoleCenter

# Module codes used for Role Center visibility (must match frontend navigation.config moduleCode)
ROLE_CENTER_MODULE_CHOICES = [
    ("dashboard", "Dashboard"),
    ("sales", "Sales"),
    ("customers", "Customers"),
    ("items", "Items"),
    ("purchases", "Purchases"),
    ("prePayments", "Prepayments"),
    ("financials", "Financials"),
    ("payments", "Payments"),
    ("expenses", "Expenses"),
    ("bankAccounts", "Bank Accounts"),
    ("loans", "Loans"),
    ("manufacturing", "Manufacturing"),
    ("manufacturingSetup", "Manufacturing Setup"),
    ("reports", "Reports"),
    ("settings", "Settings"),
    ("configPackages", "Config Packages"),
    ("trackingCodes", "Tracking Codes"),
    ("company", "Company"),
    ("userManagement", "User Management"),
    ("roles", "Roles"),
    ("profile", "Profile"),
]


class RoleCenterModuleForm(forms.ModelForm):
    """Admin form: modules as checkboxes instead of raw JSON."""

    modules = forms.MultipleChoiceField(
        choices=ROLE_CENTER_MODULE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Modules",
        help_text="Select which modules to show in the navigation for this role center.",
    )

    class Meta:
        model = RoleCenter
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and getattr(self.instance, "modules", None) is not None:
            # Ensure we only set initial values that are valid choices (preserve order)
            valid_codes = {c[0] for c in ROLE_CENTER_MODULE_CHOICES}
            self.fields["modules"].initial = [
                m for m in self.instance.modules if m in valid_codes
            ]


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "input", "placeholder": "Email", "autocomplete": "off"}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "input", "placeholder": "Password", "autocomplete": "off"}
        )
    )


class VerifyCompanyForm(forms.Form):
    company_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Company Name",
                "autocomplete": "off",
            }
        ),
    )
