from rest_framework import serializers
from devices.models import DeviceInfo, DeviceData
from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction

# -------------------------------
# DeviceInfo
# -------------------------------
class DeviceInfoSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text="Organization of this device"
    )

    class Meta:
        model = DeviceInfo
        fields = ["id", "deviceid", "active", "time", "organization"]

# -------------------------------
# DeviceData (aggregated)
# -------------------------------
class DeviceDataSerializer(serializers.Serializer):
    deviceid = serializers.CharField(
        help_text="Device ID string (e.g., JD-29ED000116)"
    )
    total_kwh = serializers.FloatField(
        help_text="Aggregated total kWh for the device"
    )
    # Optional fields for extra info if needed
    status = serializers.CharField(help_text="Device status", required=False, allow_null=True)
    time = serializers.DateTimeField(help_text="Measurement time", required=False, allow_null=True)
    txtime = serializers.CharField(help_text="Time as text (optional)", required=False, allow_blank=True, allow_null=True)

# -------------------------------
# Customer
# -------------------------------
class CustomerSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id", "name", "id_number", "phone_number", "alternate_phone_number",
            "email", "country", "location", "gender", "household_type", "household_size",
            "preferred_language", "date", "county", "sub_county", "organization"
        ]

# -------------------------------
# Sale
# -------------------------------
class SaleSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id", "customer", "registration_date", "release_date", "product_type",
            "product_name", "product_model", "product_serial_number", "purchase_mode",
            "referred_by", "sales_rep", "date", "metered", "type_of_use",
            "specific_economic_activity", "location_of_use", "payment_plan", "organization"
        ]

# -------------------------------
# Transaction
# -------------------------------
class TransactionSerializer(serializers.ModelSerializer):
    org = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Transaction
        fields = ["id", "time", "amount", "txn_id", "name", "ref", "transtime", "org"]