from django import forms
from devices.models import DeviceInfo

class ExportForm(forms.Form):

    MODEL_CHOICES = [
        ("deviceinfo", "Device Info"),
        ("devicedata", "Device Data"),
        ("customers", "Customers"),
        ("sales", "Sales"),
        ("transactions", "Transactions"),
        ("inventory", "Inventory"),
        ("organizations", "Organizations"),
        ("support", "Support Tickets"),
        ("users", "Users"),
    ]

    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"})
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "input input-bordered w-full"
        })
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "input input-bordered w-full"
        })
    )

    devices = forms.ModelMultipleChoiceField(
        queryset=DeviceInfo.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "checkbox checkbox-success"}
        )
    )

    format = forms.ChoiceField(
        choices=[("csv", "CSV"), ("excel", "Excel")],
        widget=forms.Select(attrs={"class": "select select-bordered w-full"})
    )


class CustomerSalesImportForm(forms.Form):
    file = forms.FileField(
        label="Upload Excel or CSV File",
        widget=forms.ClearableFileInput(attrs={
            "class": "file-input file-input-bordered"
        })
    )

    def clean_file(self):
        file = self.cleaned_data.get("file")

        if not file.name.endswith((".csv", ".xlsx", ".xls")):
            raise forms.ValidationError("Only CSV or Excel files are allowed.")

        return file
    
class TransactionImportForm(forms.Form):
    file = forms.FileField(
        label="Upload Excel or CSV File",
        widget=forms.ClearableFileInput(attrs={
            "class": "file-input file-input-bordered"
        })
    )

    def clean_file(self):
        file = self.cleaned_data.get("file")

        if not file.name.endswith((".csv", ".xlsx", ".xls")):
            raise forms.ValidationError("Only CSV or Excel files are allowed.")

        return file