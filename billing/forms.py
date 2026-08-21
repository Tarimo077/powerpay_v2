from django import forms
from devices.models import DeviceInfo
from inventory.models import InventoryItem
from organizations.models import Organization
from .models import Invoice, InvoiceItem, SaaSBillingRule


class HardwareInvoiceForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={"class": "select select-success w-full"})
    )
    inventory_items = forms.ModelMultipleChoiceField(
        label="Available inventory",
        queryset=InventoryItem.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "inventory-grid"}),
        help_text="Select one or more in-stock items, or enter a custom product below.",
    )
    custom_product = forms.CharField(
        required=False,
        label="Custom product",
        widget=forms.TextInput(attrs={"class": "input input-success w-full", "placeholder": "Product not in inventory"}),
    )
    custom_quantity = forms.IntegerField(
        required=False, initial=1, min_value=1,
        widget=forms.NumberInput(attrs={"class": "input input-success w-full", "min": "1"}),
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
        self.fields["inventory_items"].queryset = (
            InventoryItem.objects.filter(quantity__gt=0)
            .select_related("current_warehouse", "current_warehouse__organization")
            .order_by("name", "serial_number")
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("inventory_items") and not (cleaned.get("custom_product") or "").strip():
            raise forms.ValidationError("Select an inventory item or enter a custom product.")
        return cleaned

class SaaSInvoiceForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={"class": "select select-success w-full"})
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


    

class CustomInvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_number", "organization", "invoice_type", "status", "issue_date", "due_date", "tax"]
        widgets = {
            "invoice_number": forms.TextInput(attrs={"class": "input input-success w-full"}),
            "organization": forms.Select(attrs={"class": "select select-success w-full"}),
            "invoice_type": forms.Select(attrs={"class": "select select-success w-full"}),
            "status": forms.Select(attrs={"class": "select select-success w-full"}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "input input-success w-full"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "input input-success w-full"}),
            "tax": forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice_number"].required = False
        self.fields["invoice_number"].help_text = "Leave blank to generate an invoice number automatically."
        self.fields["organization"].queryset = Organization.objects.order_by("name")


class CustomInvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ["inventory_item", "description", "quantity", "unit_price"]
        widgets = {
            "inventory_item": forms.Select(attrs={"class": "select select-success w-full"}),
            "description": forms.TextInput(attrs={"class": "input input-success w-full", "placeholder": "Custom product or service description"}),
            "quantity": forms.NumberInput(attrs={"class": "input input-success w-full", "min": "1"}),
            "unit_price": forms.NumberInput(attrs={"class": "input input-success w-full", "step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["inventory_item"].required = False
        self.fields["inventory_item"].empty_label = "Custom product / service"
        self.fields["inventory_item"].queryset = (
            InventoryItem.objects.filter(quantity__gt=0)
            .select_related("current_warehouse")
            .order_by("name", "serial_number")
        )

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("inventory_item")
        description = (cleaned.get("description") or "").strip()
        if item and not description:
            cleaned["description"] = f"{item.name} ({item.serial_number})"
        elif not item and not description:
            self.add_error("description", "Enter a description for a custom product or service.")
        return cleaned


CustomInvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=CustomInvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
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
