from django.db import models
from organizations.models import Organization

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
    deviceid = models.CharField(max_length=100)
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
