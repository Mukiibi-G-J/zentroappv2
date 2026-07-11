from django.forms import ModelForm

from company.models import CompanyOnBoarding, Company


class CompanyOnBoardingForm(ModelForm):

    class Meta:
        model = CompanyOnBoarding
        fields = ["company_size", "business_objective", "business_category"]

    #  exclude the empty choice from the business_objective field
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business_objective"].choices = [
            choice
            for choice in self.fields["business_objective"].choices
            if choice[0] != ""
        ]
        self.fields["business_category"].choices = [
            choice
            for choice in self.fields["business_category"].choices
            if choice[0] != ""
        ]


class CompanyForm(ModelForm):
    class Meta:
        model = Company
        fields = ["name", "address", "email", "phone"]
