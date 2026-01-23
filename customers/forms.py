from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"

        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "phone_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "alternate_phone_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
            "id_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "location": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "county": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "sub_county": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "household_size": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
            "gender": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "household_type": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "preferred_language": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "organization": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Superadmin → show organization
        if user and getattr(user, "role", None) == "superadmin":
            pass
        else:
            # Normal user → hide organization field
            self.fields.pop("organization", None)

    # ✅ ADD THIS METHOD RIGHT HERE
    def save(self, commit=True):
        customer = super().save(commit=False)

        # Force organization for non-superadmins
        if self.user and getattr(self.user, "role", None) != "superadmin":
            customer.organization = self.user.organization

        if commit:
            customer.save()

        return customer
