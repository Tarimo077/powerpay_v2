from django import forms

from inventory.models import InventoryItem, Warehouse

from .models import (
    MaintenanceComment,
    MaintenancePhoto,
    MaintenanceRecord,
)
from .services import MAINTENANCE_WAREHOUSE_ID


class MaintenanceRecordForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        label="Inventory item",
        help_text="One maintenance record covers exactly one item.",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    confirm_move = forms.BooleanField(
        required=True,
        label="I understand this item will be moved to the maintenance warehouse",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-warning"}),
    )

    class Meta:
        model = MaintenanceRecord
        fields = ["item", "priority", "reported_fault"]
        widgets = {
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
