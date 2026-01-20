from django.db import models
from organizations.models import Organization

class Customer(models.Model):
    name = models.CharField(max_length=255)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    alternate_phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    country = models.CharField(max_length=100, default="Kenya")
    location = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=1, blank=True, null=True)
    household_type = models.CharField(max_length=5, blank=True, null=True)
    household_size = models.PositiveIntegerField(blank=True, null=True)
    preferred_language = models.CharField(max_length=10, blank=True, null=True)
    date = models.DateTimeField()
    county = models.CharField(max_length=100, blank=True, null=True)
    sub_county = models.CharField(max_length=100, blank=True, null=True)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="customers",
    )

    class Meta:
        db_table = "customer"
        managed = False  # IMPORTANT since we already altered the DB

    def __str__(self):
        return self.name
