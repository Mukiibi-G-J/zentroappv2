from django import forms



class UploadGLAccountsForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        file = self.cleaned_data['file']
        print(file)
        # if file.endswith('.xlsx' or '.xls'):
        #     print("true")
        #     return file
        # else:
        #     raise forms.ValidationError('File must be an Excel file')
