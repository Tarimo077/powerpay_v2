from django.db import models
from organizations.models import Organization
from django.utils import timezone
from accounts.models import User

# ----------------------
# Device Energy Data (appliatrixdata)
# ----------------------
class DeviceData(models.Model):
    id = models.BigIntegerField(primary_key=True)
    deviceid = models.CharField(max_length=100)
    kwh = models.FloatField()
    status = models.CharField(max_length=10)
    time = models.DateTimeField()
    txtime = models.CharField(max_length=20, blank=True)

    class Meta:
        managed = False  # read-only
        db_table = "appliatrixdata"


# ----------------------
# Device Info (devactivity)
# ----------------------
class DeviceInfo(models.Model):
    id = models.BigAutoField(primary_key=True)
    deviceid = models.CharField(max_length=100, unique=True)
    active = models.BooleanField()
    time = models.DateTimeField(auto_now_add=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.RESTRICT,
        db_column="organization_id",
        related_name="devices"
    )

    class Meta:
        managed = False
        db_table = "devactivity"

    def __str__(self):
        return self.deviceid


class DeviceCommandSchedule(models.Model):

    ACTION_CHOICES = [
        ("ON", "Switch ON"),
        ("OFF", "Switch OFF"),
    ]

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    devices = models.ManyToManyField(
        DeviceInfo,
        related_name="schedules"
    )

    scheduled_time = models.DateTimeField()

    executed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        User,   
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.RESTRICT,
        related_name="device_schedules"
    )

    class Meta:
        db_table = "device_command_schedule"
        managed = True
        #app_label = "devices"   # 👈 IMPORTANT

    def __str__(self):
        return f"{self.action} @ {self.scheduled_time}"
    

class TrackKwh(models.Model):
    id = models.BigAutoField(primary_key=True)
    deviceid = models.CharField(max_length=50)
    lastkwh = models.DecimalField(max_digits=12, decimal_places=6)

    class Meta:
        db_table = "trackkwh"
        managed = False  # VERY IMPORTANT → prevents Django from creating/deleting table

    def __str__(self):
        return f"{self.deviceid} - {self.lastkwh}"
    

class DeviceWalletMap(models.Model):
    device = models.OneToOneField(
        DeviceInfo,
        to_field="deviceid",
        db_column="deviceid",
        on_delete=models.CASCADE,
        related_name="wallet"
    )

    wallet_address = models.CharField(max_length=255)

    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "device_wallet_map"
        managed = False

    def __str__(self):
        return f"{self.device.deviceid} → {self.wallet_address}"