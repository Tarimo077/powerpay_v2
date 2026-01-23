from django import forms
from .models import Sale
from customers.models import Customer

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = "__all__"

        widgets = {
            "customer": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "registration_date": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "release_date": forms.DateInput(attrs={
                "type": "date",
                "class": "input input-bordered w-full"
            }),
            "product_type": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "product_name": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "product_model": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "product_serial_number": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "purchase_mode": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "referred_by": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "sales_rep": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "type_of_use": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "specific_economic_activity": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "location_of_use": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "payment_plan": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
            "organization": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # 🔐 Superadmin logic
        if user and getattr(user, "role", None) == "superadmin":
            self.fields["customer"].queryset = Customer.objects.all()
        else:
            # 👤 Normal user logic
            self.fields.pop("organization", None)

            self.fields["customer"].queryset = Customer.objects.filter(
                organization=user.organization
            )

            self.fields["referred_by"].queryset = Customer.objects.filter(
                organization=user.organization
            )

    def save(self, commit=True):
        sale = super().save(commit=False)

        # 🔒 Enforce organization
        if self.user and getattr(self.user, "role", None) != "superadmin":
            sale.organization = self.user.organization

        if commit:
            sale.save()

        return sale
