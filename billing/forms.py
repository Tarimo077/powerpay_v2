from django import forms
from devices.models import DeviceInfo
from organizations.models import Organization
from .models import SaaSBillingRule


class HardwareInvoiceForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={"class": "select select-success w-full"})
    )
    devices = forms.ModelMultipleChoiceField(
        queryset=DeviceInfo.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "device-grid"})
    )
    unit_price = forms.DecimalField(
        widget=forms.NumberInput(attrs={"class": "input input-success w-full"})
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "input input-success w-full"})
    )

    # --- NEW FIELDS ---
    hardware_tax_percent = forms.DecimalField(
        label="Hardware Tax %",
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=16.0,
        widget=forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01"})
    )

    hardware_upfront_percent = forms.DecimalField(
        label="Hardware Upfront %",
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=50.0,
        widget=forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SaaSInvoiceForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={"class": "select select-success w-full"})
    )
    devices = forms.ModelMultipleChoiceField(
        queryset=DeviceInfo.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "device-grid"})
    )
    unit_price = forms.DecimalField(
        widget=forms.NumberInput(attrs={"class": "input input-success w-full"})
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "input input-success w-full"})
    )

    # --- NEW FIELDS ---
    saas_tax_percent = forms.DecimalField(
        label="SaaS Tax %",
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=16.0,
        widget=forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01"})
    )

    saas_advance_period = forms.ChoiceField(
        label="SaaS Advance Billing",
        choices=[
            ('as_is','As-Is'),
            ('1_year','1 Year Advance'),
            ('custom','Custom Period')
        ],
        required=True,
        initial='as_is',
        widget=forms.Select(attrs={"class": "select select-success w-full"})
    )

    saas_custom_days = forms.IntegerField(
        label="Custom Period (Days)",
        required=False,
        initial=30,
        widget=forms.NumberInput(attrs={"class": "input input-success w-full", "min": "1"})
    )

    


class SaaSBillingRuleForm(forms.ModelForm):
    class Meta:
        model = SaaSBillingRule
        fields = [
            "name",
            "organization",
            "frequency",
            "custom_interval_days",
            "rate_per_device",
            "due_days",
            "next_run_at",
            "active",
            "auto_send_email",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-success w-full"}),
            "organization": forms.Select(attrs={"class": "select select-success w-full"}),
            "frequency": forms.Select(attrs={"class": "select select-success w-full"}),
            "custom_interval_days": forms.NumberInput(attrs={"class": "input input-success w-full", "min": "1"}),
            "rate_per_device": forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01", "min": "0"}),
            "due_days": forms.NumberInput(attrs={"class": "input input-success w-full", "min": "0"}),
            "next_run_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input input-success w-full"}),
            "active": forms.CheckboxInput(attrs={"class": "toggle toggle-success"}),
            "auto_send_email": forms.CheckboxInput(attrs={"class": "toggle toggle-success"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.all().order_by("name")
        if self.instance and self.instance.pk and self.instance.next_run_at:
            self.initial["next_run_at"] = self.instance.next_run_at.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        frequency = cleaned.get("frequency")
        custom_interval_days = cleaned.get("custom_interval_days")
        if frequency == "CUSTOM" and not custom_interval_days:
            self.add_error("custom_interval_days", "Enter custom interval days for a custom billing rule.")
        return cleaned