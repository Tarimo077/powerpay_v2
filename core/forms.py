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