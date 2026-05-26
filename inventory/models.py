import uuid

from django.db import models
from django.utils.timezone import now
from accounts.models import User
from organizations.models import Organization

class Warehouse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=255)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="warehouses"
    )

    class Meta:
        managed = False
        db_table = "warehouses"

    def __str__(self):
        return self.name

    
class InventoryItem(models.Model):
    TYPE_UNIQUE = "unique"
    TYPE_SHARED = "shared"
    ITEM_TYPE_CHOICES = [
        (TYPE_UNIQUE, "Unique serial number"),
        (TYPE_SHARED, "Shared serial number"),
    ]

    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100)
    product_type = models.CharField(max_length=100)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default=TYPE_UNIQUE)
    quantity = models.PositiveIntegerField(default=1)
    date_added = models.DateField(auto_now_add=True)
    current_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='inventory_items')

    def __str__(self):
        return f"{self.name} ({self.serial_number})"
    class Meta:
        managed = False
        db_table = 'inventory_items'
    @property
    def days_in_current_warehouse(self):
        # Get the most recent movement *into* the current warehouse
        last_movement_to_current = self.movements.filter(to_warehouse=self.current_warehouse).order_by('-date_moved').first()
        
        if last_movement_to_current:
            return (now() - last_movement_to_current.date_moved).days
        return (now().date() - self.date_added).days  # Fallback for items never moved
    
class InventoryMovement(models.Model):
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="movements"
    )

    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moved_from"
    )

    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        related_name="moved_to"
    )

    quantity_moved = models.PositiveIntegerField(default=1)

    moved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    date_moved = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f"{self.item.serial_number} x {self.quantity_moved} "
            f"→ {self.to_warehouse} by {self.moved_by} on {self.date_moved}"
        )

    class Meta:
        managed = False
        db_table = "inventory_movements"
        ordering = ["-date_moved"]

class InventoryDeliveryNote(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notes_sent",
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notes_received",
    )

    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField(blank=True, null=True)
    recipient_phone = models.CharField(max_length=50, blank=True, null=True)
    recipient_organization = models.CharField(max_length=255, blank=True, null=True)
    destination_address = models.TextField(blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_delivery_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    received_by_name = models.CharField(max_length=255, blank=True, null=True)
    receiver_note = models.TextField(blank=True, null=True)
    received_in_good_condition = models.BooleanField(default=False)
    received_at = models.DateTimeField(blank=True, null=True)

    @property
    def delivery_number(self):
        return f"DN-{self.id:05d}" if self.id else "DN-DRAFT"

    @property
    def is_received(self):
        return bool(self.received_at and self.received_in_good_condition)

    def __str__(self):
        return f"{self.delivery_number} - {self.recipient_name}"

    class Meta:
        managed = False
        db_table = "inventory_delivery_notes"
        ordering = ["-created_at"]


class InventoryDeliveryNoteItem(models.Model):
    delivery_note = models.ForeignKey(
        InventoryDeliveryNote,
        on_delete=models.CASCADE,
        related_name="items",
    )
    movement = models.ForeignKey(
        InventoryMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_note_items",
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_note_items",
    )

    item_name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100)
    product_type = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        managed = False
        db_table = "inventory_delivery_note_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.serial_number} x {self.quantity}"

