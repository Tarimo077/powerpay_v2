from django import forms
from devices.models import DeviceInfo
from django.db.models import Q
from core.org_checker import get_accessible_organizations

class ExportForm(forms.Form):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Full list of models
        MODEL_CHOICES = [
            ("deviceinfo", "Device Info"),
            ("devicedata", "Device Data"),
            ("testing_batches", "Device Testing Batches"),
            ("testing_batch_items", "Device Testing Batch Items"),
            ("testing_batch_dispatches", "Device Batch Dispatches"),
            ("customers", "Customers"),
            ("sales", "Sales"),
            ("transactions", "Transactions"),
            ("inventory", "Inventory"),
            ("organizations", "Organizations"),
            ("support", "Support Tickets"),
            ("users", "Users"),
        ]

        # Default device queryset. Superadmins can export/select every device.
        self.fields["devices"].queryset = (
            DeviceInfo.objects
            .all()
            .select_related("organization")
            .prefetch_related("organizations")
            .order_by("deviceid")
            .distinct()
        )

        # Restrict non-superadmins
        is_superadmin = bool(
            user and (user.is_superuser or getattr(user, "role", "") == "superadmin")
        )

        if not is_superadmin:
            allowed = [
                "deviceinfo",
                "devicedata",
                "testing_batches",
                "testing_batch_items",
                "testing_batch_dispatches",
                "customers",
                "sales",
                "transactions",
            ]
            MODEL_CHOICES = [m for m in MODEL_CHOICES if m[0] in allowed]

            if user and getattr(user, "organization", None):
                accessible_orgs = get_accessible_organizations(user)
                accessible_ids = list(accessible_orgs.values_list("id", flat=True))

                # Include both legacy/main-org devices and devices shared through
                # the DeviceInfo.organizations M2M field.
                self.fields["devices"].queryset = (
                    DeviceInfo.objects
                    .filter(
                        Q(organization_id__in=accessible_ids) |
                        Q(organizations__id__in=accessible_ids)
                    )
                    .select_related("organization")
                    .prefetch_related("organizations")
                    .order_by("deviceid")
                    .distinct()
                )
            else:
                self.fields["devices"].queryset = DeviceInfo.objects.none()

        self.fields["model"].choices = MODEL_CHOICES
        self.fields["devices"].label_from_instance = self.device_label

    @staticmethod
    def device_label(device):
        main_org = device.organization.name if getattr(device, "organization", None) else "No main org"
        view_orgs = ", ".join(org.name for org in device.organizations.all())

        if not view_orgs:
            view_orgs = main_org

        return f"{device.deviceid} | Main: {main_org} | Can view: {view_orgs}"

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
            attrs={"class": "text-white checkbox checkbox-success"}
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