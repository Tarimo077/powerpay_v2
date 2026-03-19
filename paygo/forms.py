from django import forms
from .models import PayGoSettings

class PayGoSettingsForm(forms.ModelForm):
    class Meta:
        model = PayGoSettings
        fields = ["auto_disable"]
        widgets = {
            "auto_disable": forms.CheckboxInput(attrs={"class": "toggle toggle-error"})
        }