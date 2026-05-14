from django.db import models
from django.utils import timezone
from organizations.models import Organization
from devices.models import DeviceInfo
from accounts.models import User
from transactions.models import Transaction

class Invoice(models.Model):
    TYPE_CHOICES = [
        ("HARDWARE", "Hardware"),
        ("SAAS", "SaaS"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("PAID", "Paid"),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.invoice_number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    device = models.ForeignKey(DeviceInfo, null=True, blank=True, on_delete=models.SET_NULL)

    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Receipt(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    reference = models.CharField(
        max_length=100
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Receipt {self.reference}"

class SaaSBillingRule(models.Model):
    FREQUENCY_CHOICES = [
        ("DAILY", "Every day"),
        ("WEEKLY", "Every week"),
        ("MONTHLY", "Every month"),
        ("CUSTOM", "Custom interval"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="saas_billing_rules")
    name = models.CharField(max_length=150)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    custom_interval_days = models.PositiveIntegerField(null=True, blank=True)
    rate_per_device = models.DecimalField(max_digits=10, decimal_places=2)
    due_days = models.PositiveIntegerField(default=7)
    next_run_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    auto_send_email = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]

    def __str__(self):
        return f"{self.name} - {self.organization.name}"

    @property
    def interval_days(self):
        if self.frequency == "DAILY":
            return 1
        if self.frequency == "WEEKLY":
            return 7
        if self.frequency == "MONTHLY":
            return 30
        return self.custom_interval_days or 30
