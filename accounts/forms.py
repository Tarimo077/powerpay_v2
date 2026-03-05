from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from .models import User, UserInvite
from organizations.models import Organization

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "input input-bordered w-full",
        "placeholder": "email@example.com"
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "input input-bordered w-full"
    }))

class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6)


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "class": (
                    "input input-bordered w-full border-green-300 "
                    "focus:border-green-500 focus:ring focus:ring-green-200 "
                    "rounded-lg transition bg-white dark:bg-gray-800"
                )
            }
        )
    )


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({
            "placeholder": "Enter new password",
            "class": "input input-bordered w-full border-green-300 "
                     "focus:border-green-500 focus:ring focus:ring-green-200 "
                     "rounded-lg bg-white dark:bg-gray-800 transition"
        })
        self.fields["new_password2"].widget.attrs.update({
            "placeholder": "Confirm new password",
            "class": "input input-bordered w-full border-green-300 "
                     "focus:border-green-500 focus:ring focus:ring-green-200 "
                     "rounded-lg bg-white dark:bg-gray-800 transition"
        })



# ======================
# USER & VENDOR PROFILE FORMS
# ======================
class UserProfileForm(forms.ModelForm):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
        })
    )

    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
        })
    )

    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
        })
    )

    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        user = self.instance


class InviteUserForm(forms.ModelForm):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
            "placeholder": "Enter user email"
        })
    )

    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={
            "class": "select select-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg"
        })
    )

    role = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={
            "class": "select select-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg"
        })
    )

    class Meta:
        model = UserInvite
        fields = ["email", "organization", "role"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is None:
            raise ValueError("InviteUserForm requires a user parameter")

        self.user = user

        # Superuser can pick any org and role
        if self.user.is_superuser:
            self.fields["role"].choices = [
                ("superadmin", "Super Admin"),
                ("admin", "Admin"),
                ("staff", "Staff"),
                ("support", "Support"),
            ]

        else:
            # Admin restrictions
            self.fields["organization"].queryset = Organization.objects.filter(
                id=self.user.organization_id
            )
            self.fields["organization"].initial = self.user.organization
            self.fields["organization"].disabled = True

            self.fields["role"].choices = [
                ("admin", "Admin"),
                ("staff", "Staff"),
            ]
