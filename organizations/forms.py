from django import forms
from .models import Organization

class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "address", "phone_number", "email", "logo"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "address": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
            "phone_number": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
        }
