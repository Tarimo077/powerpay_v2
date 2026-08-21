from django import forms

from inventory.models import InventoryItem, Warehouse
from organizations.models import Organization

from .models import (
    MaintenanceComment,
    MaintenancePhoto,
    MaintenanceRecord,
)
from .services import MAINTENANCE_WAREHOUSE_ID


class MaintenanceRecordForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        required=False,
        label="Inventory item (optional)",
        help_text="Select an inventory item, or leave blank and enter an external device below.",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    confirm_move = forms.BooleanField(
        required=False,
        label="I understand this item will be moved to the maintenance warehouse",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-warning"}),
    )

    class Meta:
        model = MaintenanceRecord
        fields = ["item", "organization", "item_name", "serial_number", "product_type", "priority", "reported_fault"]
        widgets = {
            "organization": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "item_name": forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "Device or item name"}),
            "serial_number": forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "Serial number / device ID"}),
            "product_type": forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "Product type or model"}),
            "priority": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "reported_fault": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 4,
                "placeholder": "Describe the reported fault",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["item"].queryset = (
            InventoryItem.objects
            .filter(quantity__gt=0)
            .exclude(current_warehouse_id=MAINTENANCE_WAREHOUSE_ID)
            .select_related("current_warehouse")
            .order_by("serial_number")
        )
        self.fields["organization"].queryset = Organization.objects.order_by("name")
        self.fields["organization"].required = False
        self.fields["item_name"].required = False
        self.fields["serial_number"].required = False

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        if item:
            if not cleaned.get("confirm_move"):
                self.add_error("confirm_move", "Confirm that the inventory item may be moved.")
        else:
            for field in ("item_name", "serial_number"):
                if not (cleaned.get(field) or "").strip():
                    self.add_error(field, "This field is required for a device outside inventory.")
        return cleaned


class MaintenanceRecordEditForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            "organization", "item_name", "serial_number", "product_type",
            "status", "priority", "reported_fault", "resolution_notes",
        ]
        widgets = {
            "organization": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "item_name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "serial_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "product_type": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "status": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "priority": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "reported_fault": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 4}),
            "resolution_notes": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 4}),
        }


class MaintenanceStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=MaintenanceRecord.STATUS_CHOICES,
        label="New status",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    note = forms.CharField(
        required=False,
        label="Status note",
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full",
            "rows": 3,
            "placeholder": "Optional note shown on the public tracking page",
        }),
    )

    return_warehouse = forms.ModelChoiceField(
        required=False,
        queryset=Warehouse.objects.none(),
        label="Return item to warehouse",
        help_text="Optional. Used when the item leaves the maintenance warehouse.",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["return_warehouse"].queryset = (
            Warehouse.objects
            .exclude(pk=MAINTENANCE_WAREHOUSE_ID)
            .order_by("name")
        )


class MaintenanceCommentForm(forms.ModelForm):
    class Meta:
        model = MaintenanceComment
        fields = ["body", "is_public"]
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "Add a comment",
            }),
            "is_public": forms.CheckboxInput(attrs={"class": "checkbox checkbox-success"}),
        }
        labels = {"is_public": "Visible on the public tracking page"}


class MaintenancePhotoForm(forms.ModelForm):
    class Meta:
        model = MaintenancePhoto
        fields = ["image", "caption", "is_public"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={
                "class": "file-input file-input-bordered w-full",
            }),
            "caption": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Optional caption",
            }),
            "is_public": forms.CheckboxInput(attrs={"class": "checkbox checkbox-success"}),
        }
        labels = {"is_public": "Visible on the public tracking page"}
