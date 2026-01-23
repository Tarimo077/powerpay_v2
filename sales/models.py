from django.db import models
from organizations.models import Organization
from customers.models import Customer

class Sale(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('EPC', 'Electric pressure cooker'),
        ('IC', 'Induction cooker'),
        ('O', 'Other'),
    ]
    
    PURCHASE_MODE_CHOICES = [
        ('C', 'Cash'),
        ('DA', 'Deposit Account'),
        ('P', 'PAYGO'),
    ]
    TYPE_OF_USE_CHOICES = [
        ('Domestic', 'Domestic'),
        ('Business', 'Business'),
        ('Other', 'Other')
    ]
    PAYMENT_PLAN_CHOICES = [
        ('Wholesale', 'Wholesale 10,600'),
        ('Plan_1', 'Plan 1: Deposit 4,500 with weekly payments of 190 for 40 weeks(12,100)'),
        ('Plan_2', 'Plan 2: Deposit 2,500 with weekly payments of 250 for 48 weeks(14,500)'),
        ('Retail', 'Retail 12,100')
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    registration_date = models.DateField()
    release_date = models.DateField(blank=True, null=True)
    product_type = models.CharField(max_length=3, choices=PRODUCT_TYPE_CHOICES)
    product_name = models.CharField(max_length=255)
    product_model = models.CharField(max_length=255)
    product_serial_number = models.CharField(max_length=255)
    purchase_mode = models.CharField(max_length=2, choices=PURCHASE_MODE_CHOICES)
    referred_by = models.ForeignKey(Customer, on_delete=models.SET_NULL, blank=True, null=True,
                                    related_name='referrals')
    sales_rep = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    metered = models.BooleanField(default=False)
    type_of_use = models.CharField(max_length=10, choices=TYPE_OF_USE_CHOICES, default='Domestic')
    specific_economic_activity = models.CharField(max_length=255, null=True, blank=True)
    location_of_use = models.CharField(max_length=255, null=True, blank=True)
    payment_plan = models.CharField(max_length=10, choices=PAYMENT_PLAN_CHOICES, blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        db_table = "sale"
        managed = False

    def __str__(self):
        return f"{self.product_serial_number} - {self.product_name}"
