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
        db_table = "warehouses"

    def __str__(self):
        return self.name

    
class InventoryItem(models.Model):
    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    product_type = models.CharField(max_length=100)
    date_added = models.DateField(auto_now_add=True)
    current_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='inventory_items')

    def __str__(self):
        return f"{self.name} ({self.serial_number})"
    class Meta:
        db_table = 'inventory_items'
    @property
    def days_in_current_warehouse(self):
        # Get the most recent movement *into* the current warehouse
        last_movement_to_current = self.movements.filter(to_warehouse=self.current_warehouse).order_by('-date_moved').first()
        
        if last_movement_to_current:
            return (now() - last_movement_to_current.date_moved).days
        return (now() - self.date_added).days  # Fallback for items never moved
    
class InventoryMovement(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True,blank=True, related_name='moved_from')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, related_name='moved_to')
    moved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_moved = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item.serial_number} → {self.to_warehouse.name} by {self.moved_by} on {self.date_moved}"
    class Meta:
        db_table = 'inventory_movements'
        ordering = ['-date_moved']