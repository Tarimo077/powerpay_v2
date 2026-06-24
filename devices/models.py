from django.db import models
from organizations.models import Organization
from accounts.models import User
from django.core.validators import RegexValidator

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
    # Legacy/primary organization column kept for backward compatibility with
    # the existing devactivity.organization_id column. New code should use
    # `organizations` below for multi-organization membership.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.RESTRICT,
        db_column="organization_id",
        related_name="primary_devices"
    )

    organizations = models.ManyToManyField(
        Organization,
        db_table="devactivity_organizations",
        related_name="devices",
        blank=True,
    )

    msisdn = models.CharField(
    max_length=13,
    null=True,
    blank=True,
    unique=True,
    db_index=True,
    validators=[
        RegexValidator(
            regex=r'^\+254[0-9]{9}$',
            message="MSISDN must start with +254 and be 13 characters long (e.g. +254123456789).",
        )
    ]
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
    

class DeviceTestingBatch(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_READY = "ready"
    STATUS_DISPATCHED = "dispatched"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_READY, "Ready for Dispatch"),
        (STATUS_DISPATCHED, "Dispatched"),
    ]

    name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_device_testing_batches",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "device_testing_batch"
        managed = True
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def total_devices(self):
        return self.items.count()

    @property
    def passed_devices(self):
        return self.items.filter(
            test_one_passed=True,
            test_two_passed=True,
        ).count()

    @property
    def packed_devices(self):
        return self.items.filter(packed=True).count()

    @property
    def ready_devices(self):
        return self.items.filter(
            test_one_passed=True,
            test_two_passed=True,
            packed=True,
        ).count()

    @property
    def is_ready_for_dispatch(self):
        total = self.total_devices
        return total > 0 and self.ready_devices == total

    def refresh_status(self):
        if self.status == self.STATUS_DISPATCHED:
            return

        total = self.total_devices

        if total == 0:
            self.status = self.STATUS_OPEN
        elif self.is_ready_for_dispatch:
            self.status = self.STATUS_READY
        elif self.items.filter(
            models.Q(test_one_passed=True)
            | models.Q(test_two_passed=True)
            | models.Q(packed=True)
        ).exists():
            self.status = self.STATUS_IN_PROGRESS
        else:
            self.status = self.STATUS_OPEN

        self.save(update_fields=["status", "updated_at"])


class DeviceTestingBatchItem(models.Model):
    batch = models.ForeignKey(
        DeviceTestingBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )

    device = models.ForeignKey(
        DeviceInfo,
        on_delete=models.CASCADE,
        related_name="testing_batch_items",
        db_constraint=False,
    )

    test_one_passed = models.BooleanField(default=False)
    test_two_passed = models.BooleanField(default=False)
    packed = models.BooleanField(default=False)

    test_one_notes = models.TextField(blank=True, null=True)
    test_two_notes = models.TextField(blank=True, null=True)
    packing_notes = models.TextField(blank=True, null=True)

    tested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tested_batch_items",
    )

    tested_at = models.DateTimeField(blank=True, null=True)
    packed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "device_testing_batch_item"
        managed = True
        unique_together = ("batch", "device")
        ordering = ["device__deviceid"]

    def __str__(self):
        return f"{self.batch.name} - {self.device.deviceid}"

    @property
    def passed_tests(self):
        return self.test_one_passed and self.test_two_passed

    @property
    def ready_for_dispatch(self):
        return self.test_one_passed and self.test_two_passed and self.packed


class DeviceBatchDispatch(models.Model):
    batch = models.OneToOneField(
        DeviceTestingBatch,
        on_delete=models.CASCADE,
        related_name="dispatch",
    )

    recipient_name = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=50, blank=True, null=True)
    recipient_organization = models.CharField(max_length=255, blank=True, null=True)
    destination = models.CharField(max_length=255, blank=True, null=True)

    dispatched_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_batch_dispatches",
    )

    dispatched_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "device_batch_dispatch"
        managed = True
        ordering = ["-dispatched_at"]

    def __str__(self):
        return f"{self.batch.name} dispatched by {self.dispatched_by}"