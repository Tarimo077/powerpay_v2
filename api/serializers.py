from rest_framework import serializers
from devices.models import DeviceInfo, DeviceData
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
import pytz

class DeviceInfoSerializer(serializers.ModelSerializer):
    ACTIVE_CHOICES = [(True, "ON"), (False, "OFF")]
    active = serializers.ChoiceField(
        choices=ACTIVE_CHOICES,
        help_text="Device state: ON (true) or OFF (false)"
    )
    organization = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text="Organization that owns this device"
    )

    class Meta:
        model = DeviceInfo
        fields = ["deviceid", "active", "time", "organization"]
        extra_kwargs = {
            "deviceid": {"help_text": "Unique device identifier"},
            "time": {"help_text": "Last update time stored in UTC"},
        }

class DeviceDataSerializer(serializers.Serializer):
    deviceid = serializers.CharField(help_text="Unique device identifier")
    total_kwh = serializers.FloatField(help_text="Aggregated total kWh for this device")
    time = serializers.SerializerMethodField(help_text="Latest measurement time in EAT")

    def get_time(self, obj):
        # Handle both model instances and dictionaries from .values()
        utc_time = obj.get("latest_time") if isinstance(obj, dict) else getattr(obj, "time", None)
        if not utc_time:
            return None
        eat = pytz.timezone("Africa/Nairobi")
        return utc_time.astimezone(eat)

class CustomerSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Customer
        fields = "__all__"

class SaleSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Sale
        fields = "__all__"

class TransactionSerializer(serializers.ModelSerializer):
    org = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Transaction
        fields = "__all__"