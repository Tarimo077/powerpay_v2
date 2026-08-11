from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

from organizations.models import Organization

from .models import ReportSchedule
from .services import PERIOD_CHOICES, accessible_org_ids, user_is_superadmin

INPUT = (
    "input input-success w-full rounded-xl bg-base-100 focus:outline-none "
    "focus:border-emerald-500"
)
SELECT = (
    "select select-success w-full rounded-xl bg-base-100 focus:outline-none "
    "focus:border-emerald-500"
)
TEXTAREA = (
    "textarea textarea-success w-full rounded-xl bg-base-100 focus:outline-none "
    "focus:border-emerald-500"
)
CHECK = "checkbox checkbox-success checkbox-sm text-white"


class ReportRequestForm(forms.Form):
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial="7d",
        widget=forms.Select(attrs={"class": SELECT}),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT}),
    )

    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        empty_label="All organizations",
        widget=forms.Select(attrs={"class": SELECT}),
    )

    include_customers = forms.BooleanField(
        required=False, initial=True, label="Customers",
        widget=forms.CheckboxInput(attrs={"class": CHECK}),
    )
    include_sales = forms.BooleanField(
        required=False, initial=True, label="Sales",
        widget=forms.CheckboxInput(attrs={"class": CHECK}),
    )
    include_inventory = forms.BooleanField(
        required=False, initial=True, label="Inventory",
        widget=forms.CheckboxInput(attrs={"class": CHECK}),
    )
    include_devices = forms.BooleanField(
        required=False, initial=True, label="Devices",
        widget=forms.CheckboxInput(attrs={"class": CHECK}),
    )
    include_transactions = forms.BooleanField(
        required=False, initial=True, label="Transactions",
        widget=forms.CheckboxInput(attrs={"class": CHECK}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.show_organization = bool(user and user_is_superadmin(user))

        if self.show_organization:
            self.fields["organization"].queryset = Organization.objects.filter(
                id__in=accessible_org_ids(user)
            ).order_by("name")
        else:
            # Everyone else stays scoped to their own accessible organizations.
            self.fields.pop("organization")

    def clean(self):
        data = super().clean()

        if data.get("period") == "custom":
            start = data.get("start_date")
            end = data.get("end_date")

            if not start or not end:
                raise ValidationError("Please provide both a start and an end date.")
            if start > end:
                raise ValidationError("The start date cannot be after the end date.")

        if not any(
            data.get(field)
            for field in (
                "include_customers",
                "include_sales",
                "include_inventory",
                "include_devices",
                "include_transactions",
            )
        ):
            raise ValidationError("Select at least one section to include in the report.")

        return data

    def selected_organization(self):
        """The chosen organization, or None for 'all organizations'."""
        if not self.show_organization:
            return None
        return self.cleaned_data.get("organization")

    def sections(self):
        data = self.cleaned_data
        return {
            "customers": bool(data.get("include_customers")),
            "sales": bool(data.get("include_sales")),
            "inventory": bool(data.get("include_inventory")),
            "devices": bool(data.get("include_devices")),
            "transactions": bool(data.get("include_transactions")),
        }


class ReportScheduleForm(forms.ModelForm):
    class Meta:
        model = ReportSchedule
        fields = [
            "name",
            "organization",
            "frequency",
            "interval_days",
            "recipients",
            "include_customers",
            "include_sales",
            "include_inventory",
            "include_devices",
            "include_transactions",
            "active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT, "placeholder": "Weekly operations report"}
            ),
            "organization": forms.Select(attrs={"class": SELECT}),
            "frequency": forms.Select(attrs={"class": SELECT}),
            "interval_days": forms.NumberInput(attrs={"class": INPUT, "min": 1}),
            "recipients": forms.Textarea(
                attrs={
                    "class": TEXTAREA,
                    "rows": 3,
                    "placeholder": "ops@example.com, manager@example.com",
                }
            ),
            "include_customers": forms.CheckboxInput(attrs={"class": CHECK}),
            "include_sales": forms.CheckboxInput(attrs={"class": CHECK}),
            "include_inventory": forms.CheckboxInput(attrs={"class": CHECK}),
            "include_devices": forms.CheckboxInput(attrs={"class": CHECK}),
            "include_transactions": forms.CheckboxInput(attrs={"class": CHECK}),
            "active": forms.CheckboxInput(attrs={"class": "toggle toggle-success"}),
        }
        labels = {
            "organization": "Organization",
            "interval_days": "Interval (days) - used when frequency is 'Every N days'",
            "recipients": "Recipients (comma separated)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.show_organization = bool(user and user_is_superadmin(user))

        if self.show_organization:
            self.fields["organization"].queryset = Organization.objects.filter(
                id__in=accessible_org_ids(user)
            ).order_by("name")
            self.fields["organization"].required = False
            self.fields["organization"].empty_label = "All organizations"
            self.fields["organization"].help_text = (
                "Leave as 'All organizations' to report on every organization you can access."
            )
        else:
            self.fields.pop("organization")

    def clean_recipients(self):
        raw = self.cleaned_data.get("recipients", "")
        emails = [e.strip() for e in raw.split(",") if e.strip()]

        if not emails:
            raise ValidationError("Add at least one recipient email address.")

        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(f"'{email}' is not a valid email address.")

        return ", ".join(emails)

    def clean(self):
        data = super().clean()

        if data.get("frequency") == ReportSchedule.FREQ_CUSTOM:
            if not data.get("interval_days"):
                raise ValidationError("Set the number of days for a custom interval.")

        if not any(
            data.get(field)
            for field in (
                "include_customers",
                "include_sales",
                "include_inventory",
                "include_devices",
                "include_transactions",
            )
        ):
            raise ValidationError("Select at least one section to include in the report.")

        return data

    def save(self, commit=True):
        schedule = super().save(commit=False)

        if not self.show_organization:
            # Non superadmins are always scoped to their own organization.
            schedule.organization = getattr(self.user, "organization", None)

        if not schedule.pk and not schedule.next_run_at:
            schedule.next_run_at = timezone.now()

        if commit:
            schedule.save()
        return schedule
