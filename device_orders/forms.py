from django import forms
from .models import DeviceOrder
from inventory.models import Warehouse


class DeviceOrderForm(forms.ModelForm):
    class Meta:
        model = DeviceOrder
        fields = ["warehouse", "product_type", "quantity", "notes"]

        widgets = {
            "warehouse": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "product_type": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "quantity": forms.NumberInput(attrs={
                "class": "input input-bordered w-full",
                "min": "1",
            }),
            "notes": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 4,
                "placeholder": "Optional notes",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and user.role == "superadmin":
            self.fields["warehouse"].queryset = Warehouse.objects.all()
        else:
            self.fields["warehouse"].queryset = Warehouse.objects.filter(
                organization=user.organization
            )


class DeviceOrderRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full",
            "rows": 4,
            "placeholder": "Reason for rejection",
        })
    )


class DeviceOrderFulfillForm(forms.Form):
    device_ids = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full",
            "rows": 8,
            "placeholder": "Enter one device ID per line, or comma-separated",
        }),
        help_text="Enter exactly the number of device IDs requested in this order.",
    )

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order

    def clean_device_ids(self):
        raw = self.cleaned_data["device_ids"]
        device_ids = []

        for token in raw.replace(",", "\n").splitlines():
            value = token.strip()
            if value and value not in device_ids:
                device_ids.append(value)

        if self.order and len(device_ids) != self.order.quantity:
            raise forms.ValidationError(
                f"This order requires exactly {self.order.quantity} device ID(s). "
                f"You entered {len(device_ids)}."
            )

        return device_ids