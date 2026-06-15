#from django.db import models

#class MeterReading(models.Model):
    #id = models.AutoField(primary_key=True)
    #meter_number = models.CharField(max_length=50)
    #timestamp = models.DateTimeField()
    #current_a = models.FloatField(null=True)
    #voltage_v = models.FloatField(null=True)
    #power_kw = models.FloatField(null=True)
    #power_factor = models.FloatField(null=True)
    #energy_kwh = models.FloatField(null=True)
    #time = models.DateTimeField()  # your generated column

    #class Meta:
        #db_table = "meter_readings"
        #managed = False  # Do not try to create/drop table

    #def __str__(self):
        #return f"{self.meter_number} @ {self.timestamp}"
    

from clickhouse_backend import models


class MeterReading(models.ClickhouseModel):
    id = models.Int32Field(primary_key=True)

    current_a = models.Float64Field(null=True)
    energy_kwh = models.Float64Field(null=True)

    # In ClickHouse this is NOT nullable because it is used in ORDER BY
    meter_number = models.StringField()

    power_kw = models.Float64Field(null=True)
    power_factor = models.Float64Field(null=True)

    # Your ClickHouse column is DateTime64(6)
    timestamp = models.DateTime64Field(null=True, precision=6)

    voltage_v = models.Float64Field(null=True)

    # In ClickHouse this is NOT nullable because it is used in PARTITION BY / ORDER BY
    time = models.DateTime64Field(precision=6)

    class Meta:
        db_table = "meter_readings_ch"
        managed = False

    def __str__(self):
        return f"{self.meter_number} @ {self.time}"