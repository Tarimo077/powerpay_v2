from django.contrib import admin

from .models import (
    MaintenanceComment,
    MaintenancePhoto,
    MaintenanceRecord,
    MaintenanceStatusUpdate,
)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "serial_number", "item_name", "status", "priority", "organization", "created_at")
    list_filter = ("status", "priority", "organization")
    search_fields = ("serial_number", "item_name", "product_type")


admin.site.register(MaintenanceStatusUpdate)
admin.site.register(MaintenanceComment)
admin.site.register(MaintenancePhoto)
