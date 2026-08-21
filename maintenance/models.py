import uuid

from django.db import models

from accounts.models import User
from inventory.models import InventoryItem, InventoryMovement, Warehouse
from organizations.models import Organization


class MaintenanceRecord(models.Model):
    STATUS_RECEIVED = "received"
    STATUS_DIAGNOSED = "diagnosed"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_AWAITING_PARTS = "awaiting_parts"
    STATUS_FIXED = "fixed"
    STATUS_UNREPAIRABLE = "unrepairable"
    STATUS_RETURNED = "returned"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_DIAGNOSED, "Diagnosed"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_AWAITING_PARTS, "Awaiting Parts"),
        (STATUS_FIXED, "Fixed"),
        (STATUS_UNREPAIRABLE, "Unrepairable"),
        (STATUS_RETURNED, "Returned"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    OPEN_STATUSES = [
        STATUS_RECEIVED,
        STATUS_DIAGNOSED,
        STATUS_IN_PROGRESS,
        STATUS_AWAITING_PARTS,
    ]

    CLOSED_STATUSES = [
        STATUS_FIXED,
        STATUS_UNREPAIRABLE,
        STATUS_RETURNED,
        STATUS_CANCELLED,
    ]

    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_CRITICAL = "critical"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_CRITICAL, "Critical"),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records",
    )

    # Snapshots so history survives later moves / deletions.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records",
    )

    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_sent",
    )

    item_name = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    product_type = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_RECEIVED,
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
    )

    reported_fault = models.TextField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)

    movement_in = models.ForeignKey(
        InventoryMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_in",
    )

    movement_out = models.ForeignKey(
        InventoryMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_out",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_maintenance_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "maintenance_records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} - {self.serial_number}"

    @property
    def reference(self):
        return f"MR-{self.id:05d}" if self.id else "MR-DRAFT"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def status_badge_class(self):
        return {
            self.STATUS_RECEIVED: "badge-info",
            self.STATUS_DIAGNOSED: "badge-info",
            self.STATUS_IN_PROGRESS: "badge-warning",
            self.STATUS_AWAITING_PARTS: "badge-warning",
            self.STATUS_FIXED: "badge-success",
            self.STATUS_RETURNED: "badge-success",
            self.STATUS_UNREPAIRABLE: "badge-error",
            self.STATUS_CANCELLED: "badge-error",
        }.get(self.status, "badge-ghost")


class MaintenanceStatusUpdate(models.Model):
    record = models.ForeignKey(
        MaintenanceRecord,
        on_delete=models.CASCADE,
        related_name="status_updates",
    )

    status = models.CharField(
        max_length=30,
        choices=MaintenanceRecord.STATUS_CHOICES,
    )

    note = models.TextField(blank=True, null=True)

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_status_updates",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "maintenance_status_updates"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.record_id} -> {self.status}"


class MaintenanceComment(models.Model):
    record = models.ForeignKey(
        MaintenanceRecord,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    body = models.TextField()
    is_public = models.BooleanField(default=True)

    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_comments",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "maintenance_comments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment on {self.record_id}"


class MaintenancePhoto(models.Model):
    record = models.ForeignKey(
        MaintenanceRecord,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    image = models.ImageField(upload_to="maintenance_photos/")
    caption = models.CharField(max_length=255, blank=True, null=True)
    is_public = models.BooleanField(default=True)

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_photos",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "maintenance_photos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Photo on {self.record_id}"
