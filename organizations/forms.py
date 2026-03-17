from django import forms
from .models import Organization, OrganizationAccess

class OrganizationForm(forms.ModelForm):
    # Multi-select for allowed orgs
    allowed_orgs = forms.ModelMultipleChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "select select-bordered w-full", "size": 5}),
        label="Can Access Organizations"
    )

    class Meta:
        model = Organization
        fields = ["name", "address", "phone_number", "email", "logo", "can_view_other_orgs"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "address": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
            "phone_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
            "can_view_other_orgs": forms.CheckboxInput(attrs={"class": "checkbox checkbox-success"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # Pre-fill allowed_orgs based on OrganizationAccess
            self.fields["allowed_orgs"].initial = [
                access.target_org.id for access in self.instance.source_access.all()
            ]

    def save(self, commit=True):
        org = super().save(commit)

        # Save allowed_orgs as OrganizationAccess
        selected_orgs = self.cleaned_data.get("allowed_orgs", [])
        # Remove old access
        OrganizationAccess.objects.filter(source_org=org).exclude(target_org__in=selected_orgs).delete()
        # Add new access
        for target_org in selected_orgs:
            OrganizationAccess.objects.get_or_create(source_org=org, target_org=target_org)

        return org