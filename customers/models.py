from django.db import models
from organizations.models import Organization

class Customer(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('P', 'Prefer not to say'),
        ('O', 'Other'),
    ]
    
    HOUSEHOLD_CHOICES = [
        ('M', 'Male headed'),
        ('F', 'Female headed'),
        ('C', 'Child headed'),
        ('O', 'Other'),
        ('P', 'Prefer not to say'),
    ]
    
    LANGUAGE_CHOICES = [
        ('EN', 'English'),
        ('SW', 'Kiswahili'),
        ('NA', 'Native'),
    ]
    name = models.CharField(max_length=255)
    id_number = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15)
    alternate_phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    country = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    household_type = models.CharField(max_length=1, choices=HOUSEHOLD_CHOICES)
    household_size = models.IntegerField()
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    date = models.DateTimeField(auto_now_add=True)
    county = models.CharField(max_length=100, null=True, blank=True)
    sub_county = models.CharField(max_length=100, null=True, blank=True)

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
