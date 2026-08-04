from django.contrib import admin

from .models import ReportRun, ReportSchedule


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "frequency", "active", "next_run_at", "last_run_at")
    list_filter = ("frequency", "active")
    search_fields = ("name", "recipients", "user__email")


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "source", "status", "period_start", "period_end")
    list_filter = ("status", "source")
