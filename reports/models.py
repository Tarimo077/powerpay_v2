from datetime import timedelta

from django.db import models
from django.utils import timezone

from accounts.models import User
from organizations.models import Organization


class ReportSchedule(models.Model):
    FREQ_DAILY = "daily"
    FREQ_WEEKLY = "weekly"
    FREQ_MONTHLY = "monthly"
    FREQ_CUSTOM = "custom_days"

    FREQUENCY_CHOICES = [
        (FREQ_DAILY, "Daily"),
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
        (FREQ_CUSTOM, "Every N days"),
    ]

    name = models.CharField(max_length=150)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="report_schedules",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="report_schedules",
        null=True,
        blank=True,
    )

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQ_WEEKLY,
    )
    interval_days = models.PositiveIntegerField(default=7)

    recipients = models.TextField(
        help_text="Comma separated email addresses",
    )

    include_customers = models.BooleanField(default=True)
    include_sales = models.BooleanField(default=True)
    include_inventory = models.BooleanField(default=True)
    include_devices = models.BooleanField(default=True)
    include_transactions = models.BooleanField(default=True)

    active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(default=timezone.now)
    last_run_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_schedules"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    # ---------------- helpers ----------------
    @property
    def recipient_list(self):
        return [e.strip() for e in (self.recipients or "").split(",") if e.strip()]

    @property
    def sections(self):
        return {
            "customers": self.include_customers,
            "sales": self.include_sales,
            "inventory": self.include_inventory,
            "devices": self.include_devices,
            "transactions": self.include_transactions,
        }

    def period_delta(self):
        if self.frequency == self.FREQ_DAILY:
            return timedelta(days=1)
        if self.frequency == self.FREQ_WEEKLY:
            return timedelta(days=7)
        if self.frequency == self.FREQ_MONTHLY:
            return timedelta(days=30)
        return timedelta(days=max(self.interval_days or 1, 1))

    def advance(self, from_time=None):
        base = from_time or timezone.now()
        self.next_run_at = base + self.period_delta()
        self.last_run_at = base
        self.save(update_fields=["next_run_at", "last_run_at", "updated_at"])


class ReportRun(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]


    SOURCE_MANUAL = "manual"
    SOURCE_SCHEDULED = "scheduled"

    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_SCHEDULED, "Scheduled"),
    ]

    schedule = models.ForeignKey(
        ReportSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="report_runs",
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    recipients = models.TextField(blank=True)
    sections_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        db_table = "report_runs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report {self.period_start:%d %b %Y} - {self.period_end:%d %b %Y}"
