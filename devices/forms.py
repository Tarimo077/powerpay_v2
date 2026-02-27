from django import forms
from .models import DeviceInfo, DeviceCommandSchedule
from inventory.models import Warehouse

class DeviceForm(forms.ModelForm):

    add_to_inventory = forms.BooleanField(
        required=False,
        label="Add to Inventory?",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-success text-white"})
    )

    inventory_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "Enter inventory name"
        })
    )

    product_type = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "e.g. Digitized Electric Pressure Cooker"
        })
    )

    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"})
    )

    class Meta:
        model = DeviceInfo
        fields = ["deviceid", "active", "organization"]

        widgets = {
            "deviceid": forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "Enter the device ID for device"}),
            "active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-success text-white"}),
            "organization": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not user or not user.is_superuser:
            self.fields.pop("organization", None)

    def clean(self):
        cleaned_data = super().clean()
        add_to_inventory = cleaned_data.get("add_to_inventory")

        if add_to_inventory:
            if not cleaned_data.get("inventory_name"):
                self.add_error("inventory_name", "Inventory name is required")
            if not cleaned_data.get("product_type"):
                self.add_error("product_type", "Product type is required")
            if not cleaned_data.get("warehouse"):
                self.add_error("warehouse", "Warehouse is required")

        return cleaned_data


class DeviceCommandScheduleForm(forms.ModelForm):
    class Meta:
        model = DeviceCommandSchedule
        fields = ["action", "devices", "scheduled_time"]
        widgets = {
            "action": forms.Select(attrs={"class": "select select-bordered w-full max-w-xs"}),
            "scheduled_time": forms.DateTimeInput(attrs={"class": "input input-bordered w-full max-w-xs form-control", "type": "datetime-local"}),
            "devices": forms.CheckboxSelectMultiple(attrs={"class": "device-grid"}),
        }