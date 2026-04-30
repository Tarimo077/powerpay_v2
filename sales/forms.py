from django import forms
from .models import Sale
from customers.models import Customer


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = "__all__"

        widgets = {
            # ❌ DO NOT USE SELECT ANYMORE (JS controls this)
            "customer": forms.HiddenInput(),
            "referred_by": forms.HiddenInput(),

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

        # Superadmin can see everything (used only for validation if needed)
        if user and getattr(user, "role", None) == "superadmin":
            self.customer_queryset = Customer.objects.all()
        else:
            org = user.organization
            self.customer_queryset = Customer.objects.filter(organization=org)

    def clean_customer(self):
        customer = self.cleaned_data.get("customer")
        if customer:
            return customer
        return None

    def clean_referred_by(self):
        referred = self.cleaned_data.get("referred_by")
        if referred:
            return referred
        return None

    def save(self, commit=True):
        sale = super().save(commit=False)

        if self.user and getattr(self.user, "role", None) != "superadmin":
            sale.organization = self.user.organization

        if commit:
            sale.save()

        return sale