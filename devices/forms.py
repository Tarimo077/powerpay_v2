from django import forms
from inventory.models import Warehouse
from organizations.models import Organization
from .models import (
    DeviceInfo,
    DeviceTestingBatch,
    DeviceBatchDispatch,
    DeviceCommandSchedule,
)
from django.db.models import Q


class DeviceTestingBatchForm(forms.ModelForm):
    devices = forms.ModelMultipleChoiceField(
        queryset=DeviceInfo.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Devices in this testing batch",
    )

    class Meta:
        model = DeviceTestingBatch
        fields = ["name", "note", "devices"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "e.g. Batch 2026-05-25",
            }),
            "note": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "Optional batch note",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and (user.is_superuser or getattr(user, "role", None) == "superadmin"):
            self.fields["devices"].queryset = DeviceInfo.objects.all().order_by("deviceid")
        elif user and getattr(user, "organization", None):
            self.fields["devices"].queryset = (
                DeviceInfo.objects
                .filter(
                    Q(organization=user.organization)
                    | Q(organizations=user.organization)
                )
                .distinct()
                .order_by("deviceid")
            )
        else:
            self.fields["devices"].queryset = DeviceInfo.objects.none()


class DeviceBatchDispatchForm(forms.ModelForm):
    class Meta:
        model = DeviceBatchDispatch
        fields = [
            "recipient_name",
            "recipient_phone",
            "recipient_organization",
            "destination",
            "note",
        ]

        widgets = {
            "recipient_name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Recipient full name",
            }),
            "recipient_phone": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Recipient phone",
            }),
            "recipient_organization": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Recipient organization",
            }),
            "destination": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Dispatch destination",
            }),
            "note": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "Optional dispatch note",
            }),
        }

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

    organizations = forms.ModelMultipleChoiceField(
        queryset=Organization.objects.none(),
        required=True,
        label="Organizations",
        help_text="Select one or more organizations that can access this device.",
        widget=forms.SelectMultiple(attrs={
            "class": "select select-bordered w-full min-h-32",
            "size": "6",
        })
    )

    class Meta:
        model = DeviceInfo
        fields = ["deviceid", "active", "organizations"]

        widgets = {
            "deviceid": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Enter the device ID for device"
            }),
            "active": forms.CheckboxInput(attrs={"class": "checkbox checkbox-success text-white"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and (user.is_superuser or getattr(user, "role", None) == "superadmin"):
            org_qs = Organization.objects.all()
        elif user and getattr(user, "organization", None):
            org_qs = Organization.objects.filter(pk=user.organization.pk)
        else:
            org_qs = Organization.objects.none()

        self.fields["organizations"].queryset = org_qs

        if self.instance and self.instance.pk:
            selected_orgs = self.instance.organizations.all()
            if selected_orgs.exists():
                self.fields["organizations"].initial = selected_orgs
            elif self.instance.organization_id:
                # Legacy fallback for rows that have not yet been backfilled into
                # the M2M join table.
                self.fields["organizations"].initial = [self.instance.organization_id]

    def clean_organizations(self):
        organizations = self.cleaned_data.get("organizations")
        if not organizations:
            raise forms.ValidationError("Select at least one organization.")
        return organizations

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

    def save(self, commit=True):
        organizations = self.cleaned_data.get("organizations")
        device = super().save(commit=False)

        # Keep the legacy devactivity.organization_id column populated with the
        # first selected organization so old code and NOT NULL DB constraints do
        # not break. The real multi-org membership is stored in `organizations`.
        if organizations:
            device.organization = organizations[0]

        if commit:
            device.save()
            device.organizations.set(organizations)

        return device


class DeviceCommandScheduleForm(forms.ModelForm):
    class Meta:
        model = DeviceCommandSchedule
        fields = ["action", "devices", "scheduled_time"]

        widgets = {
            "action": forms.Select(
                attrs={"class": "select select-bordered w-full max-w-xs"}
            ),

            "scheduled_time": forms.DateTimeInput(
                attrs={
                    "class": "input input-bordered w-full max-w-xs form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),

            "devices": forms.CheckboxSelectMultiple(
                attrs={"class": "device-grid"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["scheduled_time"].input_formats = ("%Y-%m-%dT%H:%M",)

        if self.user:
            if getattr(self.user, "role", None) == "superadmin" or self.user.is_superuser:
                self.fields["devices"].queryset = (
                    DeviceInfo.objects
                    .select_related("organization")
                    .all()
                    .distinct()
                    .order_by("deviceid")
                )
            else:
                self.fields["devices"].queryset = (
                    DeviceInfo.objects
                    .select_related("organization")
                    .filter(organizations=self.user.organization)
                    .distinct()
                    .order_by("deviceid")
                )

    def clean(self):
        cleaned_data = super().clean()
        devices = cleaned_data.get("devices")

        if not devices:
            return cleaned_data

        user_is_superadmin = bool(
            self.user
            and (
                getattr(self.user, "role", None) == "superadmin"
                or self.user.is_superuser
            )
        )

        if user_is_superadmin:
            primary_org_ids = set(
                devices.exclude(organization__isnull=True)
                .values_list("organization_id", flat=True)
            )

            if len(primary_org_ids) > 1:
                raise forms.ValidationError(
                    "Choose devices from one organization only. "
                    "A device schedule can only belong to one organization."
                )

            if not primary_org_ids:
                raise forms.ValidationError(
                    "The selected devices do not have a primary organization."
                )

        return cleaned_data


class BulkDeviceCreateForm(forms.Form):
    deviceids = forms.CharField(
        label="Device IDs",
        help_text="Enter one device ID per line, or separate device IDs with commas.",
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full min-h-44",
            "placeholder": "NEOPRS000001\nNEOPRS000002\nNEOPRS000003"
        })
    )

    active = forms.BooleanField(
        required=False,
        initial=True,
        label="Create as active",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-success text-white"})
    )

    organizations = forms.ModelMultipleChoiceField(
        queryset=Organization.objects.none(),
        label="Organizations",
        help_text="Select one or more organizations for the new devices.",
        widget=forms.SelectMultiple(attrs={
            "class": "select select-bordered w-full min-h-32",
            "size": "6",
        })
    )

    # Inventory options
    add_to_inventory = forms.BooleanField(
        required=False,
        initial=False,
        label="Add devices to inventory",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-success text-white"})
    )

    inventory_name = forms.CharField(
        required=False,
        label="Inventory Name (applied to all devices)",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"})
    )

    product_type = forms.CharField(
        required=False,
        label="Product Type (applied to all devices)",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"})
    )

    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all(),
        required=False,
        label="Warehouse (applied to all devices)",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and (user.is_superuser or getattr(user, "role", None) == "superadmin"):
            self.fields["organizations"].queryset = Organization.objects.all()
        elif user and getattr(user, "organization", None):
            self.fields["organizations"].queryset = Organization.objects.filter(pk=user.organization.pk)
            self.fields["organizations"].initial = [user.organization]
        else:
            self.fields["organizations"].queryset = Organization.objects.none()

    def clean_deviceids(self):
        raw_deviceids = self.cleaned_data["deviceids"]
        normalized = []
        seen = set()
        for token in raw_deviceids.replace(",", "\n").splitlines():
            deviceid = token.strip()
            if not deviceid:
                continue
            if deviceid not in seen:
                normalized.append(deviceid)
                seen.add(deviceid)
        if not normalized:
            raise forms.ValidationError("Enter at least one device ID.")
        return normalized

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
