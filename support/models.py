from django.db import models
from accounts.models import User
from django.utils import timezone


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    SUBJECT_CHOICES = [
        ("account", "Account Issue"),
        ("device", "Device Issue"),
        #("billing", "Billing & Payment"),
        ("technical", "Technical Problem"),
        ("feature", "Feature Request"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=80, choices=SUBJECT_CHOICES, default='account')
    description = models.TextField()
    reply = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.status}] {self.subject}"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Message on Ticket #{self.ticket.id}"