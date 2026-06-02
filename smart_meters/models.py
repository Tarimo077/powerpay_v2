from django.db import models

class MeterReading(models.Model):
    id = models.AutoField(primary_key=True)
    meter_number = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    current_a = models.FloatField(null=True)
    voltage_v = models.FloatField(null=True)
    power_kw = models.FloatField(null=True)
    power_factor = models.FloatField(null=True)
    energy_kwh = models.FloatField(null=True)
    time = models.DateTimeField()  # your generated column

    class Meta:
        db_table = "meter_readings"
        managed = False  # Do not try to create/drop table

    def __str__(self):
        return f"{self.meter_number} @ {self.timestamp}"