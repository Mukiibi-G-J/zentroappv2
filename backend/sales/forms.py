from django import forms

class FilterSalesForm(forms.Form):
    start_date = forms.DateField(required=True)
    end_date = forms.DateField(required=True)

