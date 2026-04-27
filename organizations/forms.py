from django import forms
from .models import Organization, OrganizationAccess, OrganizationAppAccess


class OrganizationForm(forms.ModelForm):

    # ORG ACCESS
    allowed_orgs = forms.ModelMultipleChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "select select-bordered w-full",
                "size": 5
            }
        ),
        label="Can Access Organizations"
    )

    # APP ACCESS
    allowed_apps = forms.MultipleChoiceField(
        choices=OrganizationAppAccess.APP_CHOICES,
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "select select-bordered w-full",
                "size": 6
            }
        ),
        label="Allowed Apps"
    )

    class Meta:
        model = Organization
        fields = [
            "name",
            "address",
            "phone_number",
            "email",
            "logo",
            "plan",  # NEW
            "can_view_other_orgs",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full",
                    "rows": 3
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "plan": forms.Select(
                attrs={"class": "select select-bordered w-full"}
            ),
            "can_view_other_orgs": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-success"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            self.fields["allowed_orgs"].initial = [
                access.target_org.id
                for access in self.instance.source_access.all()
            ]

            self.fields["allowed_apps"].initial = list(
                OrganizationAppAccess.objects.filter(
                    organization=self.instance
                ).values_list("app_name", flat=True)
            )

    def save(self, commit=True):
        org = super().save(commit)

        # ORG ACCESS
        selected_orgs = self.cleaned_data.get("allowed_orgs", [])

        OrganizationAccess.objects.filter(
            source_org=org
        ).exclude(
            target_org__in=selected_orgs
        ).delete()

        for target_org in selected_orgs:
            OrganizationAccess.objects.get_or_create(
                source_org=org,
                target_org=target_org
            )

        # APP ACCESS
        selected_apps = self.cleaned_data.get("allowed_apps", [])

        OrganizationAppAccess.objects.filter(
            organization=org
        ).exclude(
            app_name__in=selected_apps
        ).delete()

        for app in selected_apps:
            OrganizationAppAccess.objects.get_or_create(
                organization=org,
                app_name=app
            )

        return org