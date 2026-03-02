from django import forms
from devices.models import DeviceInfo

class ExportForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Full list of models
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

        # Restrict non-superadmins
        if not user or getattr(user, "role", "") != "superadmin":
            allowed = ["deviceinfo", "devicedata", "customers", "sales", "transactions"]
            MODEL_CHOICES = [m for m in MODEL_CHOICES if m[0] in allowed]

            # Restrict devices queryset to user's org
            self.fields["devices"].queryset = DeviceInfo.objects.filter(
                organization=user.organization
            )

        self.fields["model"].choices = MODEL_CHOICES

    model = forms.ChoiceField(
        choices=[],  # dynamically set in __init__
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