from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from organizations.models import Organization
from datetime import timedelta
from .managers import UserManager
import uuid

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="users"
    )

    ROLE_CHOICES = [
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("support", "Support"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # No required fields besides email

    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} ({self.email})"

class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return f"{self.user.email} - {self.otp}"
    

class UserInvite(models.Model):
    ROLE_CHOICES = [
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("support", "Support"),
    ]

    email = models.EmailField()
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_invites"
    )
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=3)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
