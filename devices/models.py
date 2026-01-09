from django.db import models

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
    id = models.BigIntegerField(primary_key=True)
    deviceid = models.CharField(max_length=100)
    active = models.BooleanField()
    time = models.DateTimeField()

    class Meta:
        managed = False  # read-only
        db_table = "devactivity"
