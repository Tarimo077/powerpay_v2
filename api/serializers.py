from rest_framework import serializers
from devices.models import DeviceInfo, DeviceWalletMap, DeviceCommandSchedule, TrackKwh
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
from organizations.models import Organization, OrganizationAccess, OrganizationAppAccess
from inventory.models import Warehouse, InventoryItem, InventoryMovement
from billing.models import Invoice, InvoiceItem, Receipt, SaaSBillingRule
from paygo.models import PayGoSettings
from support.models import Ticket, TicketMessage
import pytz
from django.utils import timezone
from smart_meters.models import MeterReading


class MeterReadingSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField(help_text="Timestamp in UTC+3 (EAT)")

    class Meta:
        model = MeterReading
        fields = [
            "meter_number",
            "timestamp",
            "current_a",
            "voltage_v",
            "power_kw",
            "power_factor",
            "energy_kwh",
        ]
        read_only_fields = fields

    def get_timestamp(self, obj):
        if obj.timestamp:
            # Convert UTC timestamp to UTC+3 (EAT)
            eat = pytz.timezone("Africa/Nairobi")
            return obj.timestamp.astimezone(eat).isoformat()
        return None


class DeviceInfoSerializer(serializers.ModelSerializer):
    ACTIVE_CHOICES = [(True, "ON"), (False, "OFF")]
    active = serializers.ChoiceField(
        choices=ACTIVE_CHOICES,
        help_text="Device state: ON (true) or OFF (false)"
    )
    organization = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text="Legacy/main organization that owns this device"
    )
    organizations = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
        help_text="Organizations that can view this device"
    )

    class Meta:
        model = DeviceInfo
        fields = ["id", "deviceid", "active", "time", "organization", "organizations"]
        extra_kwargs = {
            "deviceid": {"help_text": "Unique device identifier"},
            "time": {"help_text": "Last update time stored in UTC"},
        }


class DeviceStatusSerializer(serializers.Serializer):
    active = serializers.BooleanField(required=False, help_text="True activates the device; false deactivates it")
    action = serializers.ChoiceField(
        choices=["activate", "deactivate", "on", "off", "ON", "OFF"],
        required=False,
        help_text="Alternative to active. Use activate/deactivate or ON/OFF."
    )

    def validate(self, attrs):
        if "active" not in attrs and "action" not in attrs:
            raise serializers.ValidationError("Provide either active or action.")
        return attrs

    @property
    def target_status(self):
        if "active" in self.validated_data:
            return self.validated_data["active"]
        action = self.validated_data["action"].lower()
        return action in ["activate", "on"]


class DeviceDataSerializer(serializers.Serializer):
    deviceid = serializers.CharField(help_text="Unique device identifier")
    total_kwh = serializers.FloatField(help_text="Aggregated total kWh for this device")
    time = serializers.SerializerMethodField(help_text="Latest measurement time in EAT")

    def get_time(self, obj):
        utc_time = obj.get("latest_time") if isinstance(obj, dict) else getattr(obj, "time", None)
        if not utc_time:
            return None
        eat = pytz.timezone("Africa/Nairobi")
        return utc_time.astimezone(eat)


class DeviceCommandScheduleSerializer(serializers.ModelSerializer):
    devices = serializers.SlugRelatedField(
        many=True,
        slug_field="deviceid",
        queryset=DeviceInfo.objects.all(),
        help_text="List of device IDs to schedule"
    )
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        required=False,
        help_text="Required for superusers only when they want to choose a target organization"
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DeviceCommandSchedule
        fields = [
            "id", "action", "devices", "scheduled_time", "executed",
            "created_at", "created_by", "organization"
        ]
        read_only_fields = ["id", "executed", "created_at", "created_by"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            self.fields["devices"].queryset = self.context.get("device_queryset", DeviceInfo.objects.none())
            self.fields["organization"].queryset = self.context.get("organization_queryset", Organization.objects.none())

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        is_admin = bool(user and (user.is_superuser or getattr(user, "role", "") == "superadmin"))

        if is_admin:
            if not attrs.get("organization"):
                devices = attrs.get("devices") or []
                attrs["organization"] = devices[0].organization if devices else None
        elif user:
            attrs["organization"] = user.organization

        if not attrs.get("organization"):
            raise serializers.ValidationError({"organization": "Organization is required."})

        return attrs

    def create(self, validated_data):
        devices = validated_data.pop("devices", [])
        schedule = DeviceCommandSchedule.objects.create(**validated_data)
        schedule.devices.set(devices)
        return schedule


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


class DeviceWalletSerializer(serializers.ModelSerializer):
    deviceid = serializers.CharField(write_only=True)
    device = serializers.CharField(source="device.deviceid", read_only=True)

    class Meta:
        model = DeviceWalletMap
        fields = ["deviceid", "device", "wallet_address", "linked_at"]
        read_only_fields = ["linked_at"]

    def validate_deviceid(self, value):
        if not DeviceInfo.objects.filter(deviceid=value).exists():
            raise serializers.ValidationError("Device not found")
        return value

    def create(self, validated_data):
        deviceid = validated_data.pop("deviceid")
        device = DeviceInfo.objects.get(deviceid=deviceid)

        obj, created = DeviceWalletMap.objects.update_or_create(
            device=device,
            defaults={
                "wallet_address": validated_data["wallet_address"],
                "linked_at": timezone.now()
            }
        )

        self.context["created"] = created
        return obj


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class OrganizationAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAccess
        fields = "__all__"


class OrganizationAppAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationAppAccess
        fields = "__all__"


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = "__all__"


class InventoryItemSerializer(serializers.ModelSerializer):
    days_in_current_warehouse = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = "__all__"


class InventoryMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = "__all__"


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = "__all__"


class SaaSBillingRuleSerializer(serializers.ModelSerializer):
    interval_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = SaaSBillingRule
        fields = "__all__"


class PayGoSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayGoSettings
        fields = "__all__"


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = "__all__"


class TicketMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketMessage
        fields = "__all__"


class TrackKwhSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackKwh
        fields = "__all__"
