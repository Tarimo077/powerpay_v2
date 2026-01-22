from django.contrib import admin
from .models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'status', 'priority', 'created_at', 'updated_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('subject', 'description', 'user__username')
    ordering = ('-created_at',)
