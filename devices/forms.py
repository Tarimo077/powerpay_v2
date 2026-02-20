from django import forms
from .models import DeviceInfo, DeviceCommandSchedule

class DeviceForm(forms.ModelForm):
    class Meta:
        model = DeviceInfo
        fields = ["deviceid", "active", "organization"]

        widgets = {
            "deviceid": forms.TextInput(attrs={
                "class": "input input-bordered w-full"
            }),
            "active": forms.CheckboxInput(attrs={
                "class": "checkbox checkbox-success"
            }),
            "organization": forms.Select(attrs={
                "class": "select select-bordered w-full"
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # HARD GUARD: only superuser sees org selector
        if not user or not user.is_superuser:
            self.fields.pop("organization", None)


class DeviceCommandScheduleForm(forms.ModelForm):
    class Meta:
        model = DeviceCommandSchedule
        fields = ["action", "devices", "scheduled_time"]
        widgets = {
            "scheduled_time": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "devices": forms.CheckboxSelectMultiple(attrs={"class": "device-grid"}),
        }