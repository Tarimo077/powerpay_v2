from django.db import models
from django.utils import timezone
from accounts.models import User
from organizations.models import Organization
from inventory.models import Warehouse


class DeviceOrder(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]

    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="device_orders",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="device_orders",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="device_orders",
    )

    PRODUCT_TYPE_CHOICES = [
        ("appliatrix_board", "Appliatrix Board"),
    ]

    product_type = models.CharField(
        max_length=100,
        choices=PRODUCT_TYPE_CHOICES,
        default="appliatrix_board",
    )
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")

    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_device_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    fulfilled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fulfilled_device_orders",
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "device_orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.product_type}"

    @property
    def can_be_reviewed(self):
        return self.status == "submitted"

    @property
    def can_be_fulfilled(self):
        return self.status == "approved"