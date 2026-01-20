from django.db import models
from organizations.models import Organization
from customers.models import Customer

class Sale(models.Model):
    registration_date = models.DateField()
    release_date = models.DateField()
    product_type = models.CharField(max_length=50)
    product_name = models.CharField(max_length=100)
    product_model = models.CharField(max_length=100)
    product_serial_number = models.CharField(max_length=100, unique=True)
    purchase_mode = models.CharField(max_length=10)
    referred_by_id = models.IntegerField(blank=True, null=True)
    sales_rep = models.CharField(max_length=100)
    date = models.DateTimeField()
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    location_of_use = models.CharField(max_length=100, blank=True)
    metered = models.BooleanField(default=False)
    specific_economic_activity = models.TextField(blank=True)
    type_of_use = models.CharField(max_length=50, blank=True)
    payment_plan = models.CharField(max_length=50)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        db_table = "sale"
        managed = False

    def __str__(self):
        return f"{self.product_serial_number} - {self.product_name}"
