from django import forms
from .models import Warehouse, InventoryItem, InventoryMovement


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "location", "organization"]


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "serial_number", "product_type", "current_warehouse"]


class InventoryMoveForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ["to_warehouse", "note"]
