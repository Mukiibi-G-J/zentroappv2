from django import forms
from items.models import Item, ItemJournal, UnitOfMeasure


class FileUploadForm(forms.Form):
    file = forms.FileField()


# --------------------------------  web forms  -------------------------------- #
# class ItemImagesForm(ModelForm):


class ItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.all()
        self.fields["unit_of_measure"].label_from_instance = (
            lambda obj: f"{obj.international_stnd_code}:{obj.description}"
        )
        self.fields["unit_of_measure"].widget.attrs["class"] = "input"
        self.fields["unit_of_measure"].widget.attrs["placeholder"] = "Enter unit description"
        self.fields["unit_of_measure"].widget.attrs["required"] = "required"

    class Meta:
        model = Item
        fields = [
            "item_name",
            "type",
            "item_category",
            "unit_price",
            "description",
            "unit_of_measure",
        ]

    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": "upload-input draggable",
                "accept": "image/*",
            }
        ),
    )
    

class ItemJournalForm(forms.ModelForm):
    class Meta:
        model = ItemJournal
        fields = '__all__'
        widgets = {
            'quantity': forms.TextInput(attrs={
                'class': 'numeric-input',
                'type': 'text'
            }),
            'unit_amount': forms.TextInput(attrs={
                'class': 'numeric-input',
                'type': 'text'
            }),
            'amount': forms.TextInput(attrs={
                'class': 'numeric-input',
                'type': 'text',
                'readonly': 'readonly'
            }),
            'unit_cost': forms.TextInput(attrs={
                'class': 'numeric-input',
                'type': 'text'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize numeric fields with default values if None
        numeric_fields = ['quantity', 'unit_amount', 'amount', 'unit_cost']
        for field in numeric_fields:
            if self.initial.get(field) is None:
                self.initial[field] = 0

    def clean(self):
        cleaned_data = super().clean()
        try:
            # Convert string values to appropriate types
            if 'quantity' in cleaned_data:
                cleaned_data['quantity'] = int(str(cleaned_data['quantity']).replace(',', ''))
            
            if 'unit_amount' in cleaned_data:
                cleaned_data['unit_amount'] = float(str(cleaned_data['unit_amount']).replace(',', ''))
            
            if 'unit_cost' in cleaned_data:
                cleaned_data['unit_cost'] = float(str(cleaned_data['unit_cost']).replace(',', ''))
            
            # Calculate amount
            if cleaned_data.get('quantity') and cleaned_data.get('unit_amount'):
                cleaned_data['amount'] = cleaned_data['quantity'] * cleaned_data['unit_amount']
            
            print("Form cleaned data:", cleaned_data)
            
        except (ValueError, TypeError) as e:
            raise forms.ValidationError(f"Invalid numeric value: {str(e)}")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Ensure numeric values are properly set
        if self.cleaned_data.get('quantity'):
            instance.quantity = self.cleaned_data['quantity']
        if self.cleaned_data.get('unit_amount'):
            instance.unit_amount = self.cleaned_data['unit_amount']
        if self.cleaned_data.get('amount'):
            instance.amount = self.cleaned_data['amount']
        if self.cleaned_data.get('unit_cost'):
            instance.unit_cost = self.cleaned_data['unit_cost']
        
        if commit:
            instance.save()
        
        return instance


class UnitOfMeasureForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ["description", "international_stnd_code"]
